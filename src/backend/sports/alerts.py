"""
Alerts for underpriced leaders.

An underpriced leader is a team that is AHEAD on the scoreboard while the market still has it
weighted to lose (priced under 50%): the crowd is anchored to the pregame label while the game
has moved on. This module decides which live teams qualify, avoids repeating itself, stores each
alert for the page, and emails it when SMTP is set up.
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select

from src.backend.config import settings
from src.backend.database import async_session_factory
from src.backend.models import Alert
from src.backend.notify import send_email
from src.backend.sports.cfb import RushAnomaly, RushEdge, LEAGUES, FirstScore, Signal, scan_live
from src.backend.sports.live_scores import fetch_scoreboards, match_game, norm

logger = logging.getLogger(__name__)

NAG_MIN_MINUTES = 5  # repeat alerts for an improving setup are at least this far apart
CONFIRM_SECONDS = 45  # the condition must still hold this long after it was first seen
_pending: dict[tuple[str, str], float] = {}  # (game id, team) -> when it first qualified

HIGH_WIN_PROB = 0.60  # ESPN also has the leader as a clear favorite while the market has it to lose


def is_trailing_longshot(sig: Signal) -> bool:
    """College football only: down by a score or less, and the market has it under 20%."""
    g = sig.game
    other = g.away if sig.team == g.home.name else g.home
    clock_out = (g.period >= 4 and g.seconds_left is not None and g.seconds_left < 60
                 and g.possession == other.name)  # under a minute and the leader holds the ball: they can run it out
    return (sig.league == "cfb" and -settings.ALERT_TRAIL_MAX_DEFICIT <= sig.margin < 0
            and sig.market_price < settings.ALERT_TRAIL_MAX_PRICE and not clock_out)


def priority_for(sig: Signal, max_price: float, min_lead: int = 5) -> Optional[str]:
    """None when the signal is not alert-worthy; otherwise "normal" or "high".

    Worthy means the team is ahead by at least ``min_lead`` points (default 5) and the
    market price is below ``max_price`` (default 50%, so the market still has it weighted to lose).
    It is high priority when ESPN's live win probability also has the team as a clear favorite.
    A college football team trailing by one score (8 or fewer) and priced under 20% is also worthy.
    """
    if is_trailing_longshot(sig):
        return "normal"
    if sig.margin < min_lead or sig.market_price >= max_price:
        return None
    return "high" if sig.espn_win_prob >= HIGH_WIN_PROB else "normal"


def confirmed(pending: dict[tuple[str, str], float], key: tuple[str, str], qualifies: bool, now: float, hold: float) -> bool:
    """True once ``key`` has qualified continuously for ``hold`` seconds.

    A score can be posted and then reversed (a touchdown called back), so the first reading is
    only remembered; an alert goes out when a later scan still agrees. Not qualifying clears it.
    """
    if not qualifies:
        pending.pop(key, None)
        return False
    first = pending.setdefault(key, now)
    return now - first >= hold


_had_ball: dict[tuple[str, str], bool] = {}  # (league:game, team) -> had the ball at the last scan


def got_the_ball(key: tuple[str, str], sig: Signal) -> bool:
    """True when the team has the ball now and did not at the last scan (a turnover or a stop)."""
    now_has = sig.game.possession == sig.team
    before = _had_ball.get(key)
    _had_ball[key] = now_has
    return now_has and before is False


def improved(last, sig: Signal, now: datetime, ball: bool = False) -> bool:
    """A repeat alert is allowed inside the cooldown when the situation got better since the last one.

    Better means the team is 3 or more points further ahead (or closer, for a trailing team), or the price
    fell 5 or more points with the margin no worse. At least NAG_MIN_MINUTES apart so it cannot spam.
    """
    created, margin, price = last
    if ball and sig.margin < 0 and now - created >= timedelta(minutes=1):
        return True  # a trailing team just got the ball back: worth another look right away
    if now - created < timedelta(minutes=NAG_MIN_MINUTES):
        return False
    margin = margin if margin is not None else sig.margin
    return sig.margin - margin >= 3 or (price is not None and price - sig.market_price >= 0.05 and sig.margin >= margin)


def in_cooldown(previous: list[datetime], now: datetime, minutes: int) -> bool:
    return any(now - t < timedelta(minutes=minutes) for t in previous)


def headline(sig: Signal) -> str:
    g = sig.game
    return f"{g.away.name} {g.away.score} - {g.home.name} {g.home.score}"


def _vs_market(sig: Signal) -> str:
    """Plain words for how ESPN's number compares with the market's."""
    diff = round((sig.espn_win_prob - sig.market_price) * 100)
    if diff > 0:
        return f"ESPN has this team {diff} points ABOVE the market: the market looks too low."
    if diff < 0:
        return f"ESPN has this team {-diff} points below the market: ESPN agrees it is an underdog."
    return "ESPN and the market agree."


def message_for(sig: Signal, priority: str) -> tuple[str, str]:
    """(subject, body) for an alert."""
    tag = "Underpriced HIGH" if priority == "high" else "Underpriced"
    trailing = sig.margin < 0
    if trailing:
        tag = "Longshot"
    subject = (f"[{tag}] {sig.team} down {-sig.margin} with the game still open, priced at {sig.market_price * 100:.0f}% "
               f"(ESPN {sig.espn_win_prob * 100:.0f}%)") if trailing else (f"[{tag}] {sig.team} up {sig.margin} but still priced to lose at {sig.market_price * 100:.0f}% "
               f"(ESPN {sig.espn_win_prob * 100:.0f}%)")
    body = (
        f"{headline(sig)}  ({sig.game.detail})\n\n"
        f"{sig.team} is {'trailing by ' + str(-sig.margin) if trailing else 'leading by ' + str(sig.margin)}.\n"
        f"Market price: {sig.market_price * 100:.0f}%  |  ESPN live win probability: {sig.espn_win_prob * 100:.0f}%\n"
        f"{_vs_market(sig)}\n"
        f"{'Ball: ' + sig.game.possession + chr(10) if sig.game.possession else ''}"
        f"Pregame label favorite: {sig.label_favorite or 'none'} ({sig.label_basis})"
        f"{' -> this team is the pregame underdog' if sig.is_label_underdog else ''}\n"
        f"Market: {sig.market_slug}\n"
    )
    return subject, body


async def dispatch(signals: list[Signal], league: str = "cfb") -> list[Alert]:
    """Create (and email) an alert for each qualifying signal that is not in its cooldown."""
    if not settings.ALERTS_ENABLED:
        return []
    created: list[Alert] = []
    now = datetime.utcnow()
    tick = time.monotonic()
    seen = set()
    async with async_session_factory() as session:
        for sig in signals:
            priority = priority_for(sig, settings.ALERT_MAX_PRICE, settings.ALERT_MIN_LEAD)
            key = (f"{league}:{sig.game.event_id}", sig.team)
            seen.add(key)
            ball = got_the_ball(key, sig)
            if not confirmed(_pending, key, priority is not None, tick, CONFIRM_SECONDS) or not priority:
                continue
            prior = (await session.execute(
                select(Alert.created_at, Alert.margin, Alert.market_price)
                .where(Alert.game_id == sig.game.event_id, Alert.team == sig.team)
                .order_by(Alert.created_at.desc())
            )).all()
            if prior and in_cooldown([r[0] for r in prior], now, settings.ALERT_COOLDOWN_MINUTES) \
                    and not improved(prior[0], sig, now, ball):
                continue
            subject, body = message_for(sig, priority)
            alert = Alert(
                priority=priority, sport=LEAGUES[sig.league]["sport"], game_id=sig.game.event_id, team=sig.team,
                title=headline(sig), espn_win_prob=sig.espn_win_prob, market_price=sig.market_price, gap=sig.gap,
                margin=sig.margin, detail=f"{sig.game.detail} | label favorite: {sig.label_favorite or 'none'} ({sig.label_basis})",
                market_slug=sig.market_slug, delivery=await send_email(subject, body),
            )
            session.add(alert)
            created.append(alert)
        await session.commit()
    for key in [k for k in _pending if k[0].startswith(f"{league}:") and k not in seen
              and k[1] != "first-score" and not k[1].startswith(("rush:", "anom:"))]:  # a game of this league that left the board
        _pending.pop(key, None)
    return created


FIRST_SCORE = "first_score_upset"


def first_score_message(ev: FirstScore) -> tuple[str, str]:
    g, r = ev.game, ev.ranked
    score = f"{g.away.name} {g.away.score} - {g.home.name} {g.home.score}"
    price = f"priced {ev.ranked_price * 100:.0f}% now" if ev.ranked_price is not None else "price not found"
    subject = f"[Ranked scored on first] #{r.rank} {r.name} trailing unranked {ev.scorer.name} ({price})"
    lines = [
        f"{score}  ({g.detail})",
        "",
        f"#{r.rank} {r.name} was scored on first by unranked {ev.scorer.name}.",
        f"First score: {ev.play}",
        f"Market: {r.name} {price}" + (f"  |  ESPN live win probability: {ev.espn_win_prob * 100:.0f}%" if ev.espn_win_prob is not None else ""),
        f"Market slug: {ev.market_slug}",
    ]
    return subject, "\n".join(lines) + "\n"


RUSH_EDGE = "rush_edge"


def rush_edge_message(ev: RushEdge) -> tuple[str, str]:
    g, t = ev.game, ev.team
    price = f"priced {ev.price * 100:.0f}%" if ev.price is not None else "price not found"
    subject = f"[Ground game] {t.name} averaging {ev.ypc:.1f} yards a carry vs {ev.other.name} {ev.other_ypc:.1f} ({price})"
    body = (
        f"{g.away.name} {g.away.score} - {g.home.name} {g.home.score}  ({g.detail})\n\n"
        f"{t.name}: {ev.ypc:.1f} yards a carry on {ev.carries} carries. {ev.other.name}: {ev.other_ypc:.1f}.\n"
        f"Market: {t.name} {price}"
        + (f"  |  ESPN live win probability: {ev.espn_win_prob * 100:.0f}%" if ev.espn_win_prob is not None else "")
        + f"\nMarket slug: {ev.market_slug}\n"
    )
    return subject, body


def anomaly_message(ev: RushAnomaly) -> tuple[str, str]:
    g, t = ev.game, ev.team
    price = f"priced {ev.price * 100:.0f}%" if ev.price is not None else "price not found"
    subject = (f"[Anomaly] {t.name} running {ev.ypc:.1f} a carry on {ev.defense.name}, which normally allows "
               f"{ev.allowed_ypc:.1f} ({price})")
    body = (
        f"{g.away.name} {g.away.score} - {g.home.name} {g.home.score}  ({g.detail})\n\n"
        f"{t.name}: {ev.ypc:.1f} yards a carry on {ev.carries} carries.\n"
        f"{ev.defense.name}'s defense has allowed {ev.allowed_ypc:.1f} a carry over {ev.allowed_games} games this season.\n"
        f"Market: {t.name} {price}"
        + (f"  |  ESPN live win probability: {ev.espn_win_prob * 100:.0f}%" if ev.espn_win_prob is not None else "")
        + f"\nMarket slug: {ev.market_slug}\n"
    )
    return subject, body


RUSH_ANOMALY = "rush_anomaly"


async def _dispatch_team_events(events: list, cls, kind: str, prefix: str, message, detail) -> list[Alert]:
    """One alert per game and team for ``cls`` events, after the confirmation hold."""
    if not settings.ALERTS_ENABLED:
        return []
    created: list[Alert] = []
    tick = time.monotonic()
    async with async_session_factory() as session:
        mine = [e for e in events if isinstance(e, cls)]
        live = {(f"{e.league}:{e.game.event_id}", f"{prefix}{e.team.name}") for e in mine}
        for k in [k for k in _pending if k[1].startswith(prefix) and k not in live]:  # event gone: start over
            _pending.pop(k, None)
        for ev in mine:
            key = (f"{ev.league}:{ev.game.event_id}", f"{prefix}{ev.team.name}")
            if not confirmed(_pending, key, True, tick, CONFIRM_SECONDS):
                continue
            seen = (await session.execute(
                select(Alert.id).where(Alert.kind == kind, Alert.game_id == ev.game.event_id, Alert.team == ev.team.name)
            )).first()
            if seen:
                continue
            subject, body = message(ev)
            g = ev.game
            alert = Alert(
                kind=kind, priority="normal", sport=LEAGUES[ev.league]["sport"], game_id=g.event_id, team=ev.team.name,
                title=f"{g.away.name} {g.away.score} - {g.home.name} {g.home.score}",
                espn_win_prob=ev.espn_win_prob or 0.0, market_price=ev.price or 0.0, gap=0.0,
                margin=ev.team.score - (g.away if ev.team is g.home else g.home).score,
                detail=detail(ev), market_slug=ev.market_slug, delivery=await send_email(subject, body),
            )
            session.add(alert)
            created.append(alert)
        await session.commit()
    return created


async def dispatch_rush_edges(events: list) -> list[Alert]:
    """A team at 5+ yards a carry while the other is not."""
    return await _dispatch_team_events(
        events, RushEdge, RUSH_EDGE, "rush:", rush_edge_message,
        lambda ev: f"{ev.team.name} {ev.ypc:.1f} yds/carry on {ev.carries} carries vs {ev.other.name} {ev.other_ypc:.1f}")


async def dispatch_rush_anomalies(events: list) -> list[Alert]:
    """An offense running far above what the defense across from it usually allows."""
    return await _dispatch_team_events(
        events, RushAnomaly, RUSH_ANOMALY, "anom:", anomaly_message,
        lambda ev: f"{ev.team.name} {ev.ypc:.1f} yds/carry vs {ev.defense.name} season allowed {ev.allowed_ypc:.1f}")


async def dispatch_first_scores(events: list[FirstScore]) -> list[Alert]:
    """One alert (and email) per game when an unranked team scores first on a ranked team."""
    if not settings.ALERTS_ENABLED:
        return []
    created: list[Alert] = []
    tick = time.monotonic()
    async with async_session_factory() as session:
        for ev in (e for e in events if isinstance(e, FirstScore)):
            key = (ev.game.event_id, "first-score")
            if not confirmed(_pending, key, True, tick, CONFIRM_SECONDS):
                continue
            seen = (await session.execute(
                select(Alert.id).where(Alert.kind == FIRST_SCORE, Alert.game_id == ev.game.event_id)
            )).first()
            if seen:
                continue
            subject, body = first_score_message(ev)
            g, r = ev.game, ev.ranked
            alert = Alert(
                kind=FIRST_SCORE, priority="normal", sport=LEAGUES[ev.league]["sport"], game_id=g.event_id, team=r.name,
                title=f"{g.away.name} {g.away.score} - {g.home.name} {g.home.score}",
                espn_win_prob=ev.espn_win_prob or 0.0, market_price=ev.ranked_price or 0.0, gap=0.0,
                margin=r.score - ev.scorer.score, detail=f"#{r.rank} {r.name} scored on first by unranked {ev.scorer.name}: {ev.play}",
                market_slug=ev.market_slug, delivery=await send_email(subject, body),
            )
            session.add(alert)
            created.append(alert)
        await session.commit()
    return created


def standing(title: str, team: str, boards: list) -> Optional[dict]:
    """Where the alerted team stands now: its game, its margin, and the game state. None if not found."""
    game = match_game(title, boards)
    if not game:
        return None
    n = norm(team)
    mine = next((g for g in (game["away"], game["home"]) if n in g["tokens"] or any(t in n for t in g["tokens"])), None)
    if not mine:
        return None
    other = game["home"] if mine is game["away"] else game["away"]
    return {"game": game, "margin": mine["score"] - other["score"], "state": game["state"]}


def verdict(margin: int, state: str, min_lead: int, trailing: bool = False) -> str:
    """What should happen to an active alert: keep it, retract it, or let it expire."""
    if state == "post":
        return "expired"  # the game is over; the alert was true when raised
    if trailing:  # a longshot alert holds while the team is within a score or ahead
        return "retracted" if margin < -settings.ALERT_TRAIL_MAX_DEFICIT else "keep"
    return "retracted" if margin < min_lead else "keep"


async def retract_stale() -> int:
    """Retract active alerts whose lead has gone while the game is still on; expire finished ones.

    A reversed touchdown or a correction in the feed must not leave a false alert looking current.
    If the alert had been emailed, a correction email goes out too.
    """
    boards = await fetch_scoreboards()
    now = datetime.utcnow()
    changed = 0
    async with async_session_factory() as session:
        rows = (await session.execute(
            select(Alert).where(Alert.status == "active", Alert.kind == "underpriced_leader",
                                Alert.created_at >= now - timedelta(hours=8))
        )).scalars().all()
        for a in rows:
            st = standing(a.title, a.team, boards)
            if not st:
                continue
            action = verdict(st["margin"], st["state"], settings.ALERT_MIN_LEAD, trailing=(a.margin or 0) < 0)
            if action == "keep":
                continue
            g = st["game"]
            a.status = action
            if action == "retracted":
                a.retracted_at = now
                a.retract_note = f"Score now {g['away']['name']} {g['away']['score']} - {g['home']['name']} {g['home']['score']} ({g['detail']})"
                if a.delivery.startswith("emailed"):
                    await send_email(f"[RETRACTED] {a.team} is no longer ahead",
                                     f"The earlier alert for {a.team} is withdrawn: the lead is gone.\n{a.retract_note}\n"
                                     f"(Alert was: {a.title}, raised {a.created_at:%H:%M} UTC.)")
            changed += 1
        await session.commit()
    return changed


async def scan_and_alert() -> int:
    """One pass over every league: scan for gaps, then raise alerts. Returns how many were raised."""
    raised = 0
    for league in LEAGUES:
        try:
            events: list[FirstScore] = []
            raised += len(await dispatch(await scan_live(league=league, all_signals=True, events=events), league))
            raised += len(await dispatch_first_scores(events))
            raised += len(await dispatch_rush_edges(events))
            raised += len(await dispatch_rush_anomalies(events))
        except Exception as e:  # one league failing must not stop the others
            logger.warning(f"Alert scan failed for {league}: {e}")
    try:
        await retract_stale()
    except Exception as e:
        logger.warning(f"Alert retraction pass failed: {e}")
    return raised

"""The AI inside the app: NanoGPT (OpenAI-compatible) fed with what the real-time layer has stored in SQL.

The model gets the latest reading of each live game, its recent plays, recent price jumps and active alerts, and
answers the user's question from that. It is told to report what the data shows and not to pick bets.
"""
from datetime import datetime, timedelta
from typing import Any, Optional

import time

import httpx
from sqlalchemy import func, select

from src.backend.config import settings
from src.backend.database import async_session_factory
from src.backend.models import Alert, GamePlay, GameSnapshot, PriceJump

SYSTEM_PROMPT = (
    "You are the analyst inside a sports-market tracking app. The user trades binary Polymarket sports markets "
    "(MLB, college football, NFL, tennis) by buying price dips and selling the bounce; the game result itself does "
    "not matter to them, the price path does. Use ONLY the data given. Report what changed, how the market price "
    "reacted, whether price and game state disagree, and what looks unusual (for example a team running far above "
    "what its defense allows, or a price that jumped before the score did). Do not tell the user what to bet and do "
    "not pick winners. Be brief: short paragraphs or a few bullets. If the data does not answer the question, say so."
)


class AiNotConfigured(Exception):
    pass


def _pct(v: Optional[float]) -> str:
    return "?" if v is None else f"{v * 100:.0f}%"


def format_snapshot(s: dict[str, Any]) -> str:
    box = []
    for side in ("away", "home"):
        if s.get(f"{side}_rush_carries"):
            box.append(f"{side} rush {s.get(f'{side}_rush_yards')}y/{s.get(f'{side}_rush_carries')} carries")
    sources = " ".join(f"{n}={s[k]}" for n, k in (("espn", None), ("polymarket", "poly_score"), ("thescore", "ts_score"), ("ncaa", "ncaa_score")) if k and s.get(k))
    return (
        f"[{s['league']} game {s['game_id']}] {s['away_team']} {s['away_score']} @ {s['home_team']} {s['home_score']} | "
        f"{s.get('detail') or ''} | ball: {s.get('possession') or '-'} | price away {_pct(s.get('away_price'))} "
        f"home {_pct(s.get('home_price'))} | home win prob {_pct(s.get('home_win_prob'))}"
        + (f" | {'; '.join(box)}" if box else "") + (f" | other sources: {sources}" if sources else "")
    )


def format_context(snaps: list[dict], plays: list[dict], jumps: list[dict], alerts: list[dict]) -> str:
    lines = ["LIVE GAMES (latest reading):"] + [format_snapshot(s) for s in snaps] if snaps else ["No live games with a reading in the last 20 minutes."]
    if plays:
        lines += ["", "RECENT PLAYS (oldest first):"] + [
            f"- q{p['period'] or '?'} {p['clock'] or ''} {p['text']} ({p['yards']} yds)" if p.get("yards") is not None
            else f"- q{p['period'] or '?'} {p['clock'] or ''} {p['text']}" for p in plays]
    if jumps:
        lines += ["", "RECENT PRICE JUMPS (market reacting):"] + [
            f"- {j['slug']} {j['outcome']}: {j['from_price'] * 100:.0f}% -> {j['to_price'] * 100:.0f}% in {j['window_ms']} ms" for j in jumps]
    if alerts:
        lines += ["", "ACTIVE ALERTS:"] + [f"- {a['title']} | {a['team']} margin {a['margin']} price {_pct(a['market_price'])}" for a in alerts]
    return "\n".join(lines)


def _row(obj: Any, cols: list[str]) -> dict[str, Any]:
    return {c: getattr(obj, c) for c in cols}


async def gather_context(game_id: Optional[str] = None, league: Optional[str] = None) -> str:
    """Read the latest state from SQL and format it for the model."""
    since = datetime.utcnow() - timedelta(minutes=20)
    async with async_session_factory() as session:
        latest = select(func.max(GameSnapshot.id)).where(GameSnapshot.created_at > since).group_by(GameSnapshot.league, GameSnapshot.game_id)
        if game_id:
            latest = latest.where(GameSnapshot.game_id == game_id)
        if league:
            latest = latest.where(GameSnapshot.league == league)
        snaps = (await session.execute(select(GameSnapshot).where(GameSnapshot.id.in_(latest)).order_by(GameSnapshot.id.desc()).limit(8))).scalars().all()
        snap_dicts = [vars(s) for s in snaps]
        play_q = select(GamePlay).order_by(GamePlay.id.desc()).limit(14)
        if game_id:
            play_q = play_q.where(GamePlay.game_id == game_id)
        elif snaps:
            play_q = play_q.where(GamePlay.game_id.in_([s.game_id for s in snaps]))
        plays = list(reversed((await session.execute(play_q)).scalars().all()))
        jumps = (await session.execute(select(PriceJump).where(PriceJump.created_at > since).order_by(PriceJump.id.desc()).limit(10))).scalars().all()
        alerts = (await session.execute(select(Alert).where(Alert.status == "active").order_by(Alert.id.desc()).limit(8))).scalars().all()
    return format_context(
        snap_dicts,
        [_row(p, ["period", "clock", "text", "yards"]) for p in plays],
        [_row(j, ["slug", "outcome", "from_price", "to_price", "window_ms"]) for j in jumps],
        [_row(a, ["title", "team", "margin", "market_price"]) for a in alerts],
    )


_models_cache: dict[str, Any] = {"at": 0.0, "ids": []}


async def list_models() -> list[str]:
    """Every model id available under the NanoGPT key (cached for 10 minutes)."""
    if not settings.NANOGPT_API_KEY:
        raise AiNotConfigured("Set NANOGPT_API_KEY in .env to turn the AI on.")
    if time.time() - _models_cache["at"] < 600 and _models_cache["ids"]:
        return _models_cache["ids"]
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(f"{settings.NANOGPT_BASE_URL}/models", headers={"Authorization": f"Bearer {settings.NANOGPT_API_KEY}"})
    resp.raise_for_status()
    ids = sorted(m["id"] for m in resp.json().get("data", []))
    _models_cache.update(at=time.time(), ids=ids)
    return ids


def extract_answer(data: dict[str, Any]) -> str:
    """The reply text. Some models put their text in a reasoning field when the normal one is empty."""
    choice = (data.get("choices") or [{}])[0]
    msg = choice.get("message") or {}
    text = (msg.get("content") or "").strip() or (msg.get("reasoning_content") or msg.get("reasoning") or "").strip()
    if not text:
        raise EmptyAnswer(f"The model returned no text (finish reason: {choice.get('finish_reason')}).")
    return text


class EmptyAnswer(Exception):
    pass


async def ask(question: str, context: str, model: str) -> dict[str, Any]:
    """Send the question and the stored context to the chosen NanoGPT model and return its answer."""
    if not settings.NANOGPT_API_KEY:
        raise AiNotConfigured("Set NANOGPT_API_KEY in .env to turn the AI on.")
    payload = {
        "model": model, "temperature": 0.2, "max_tokens": 2000,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"{context}\n\nQUESTION: {question}"},
        ],
    }
    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(
            f"{settings.NANOGPT_BASE_URL}/chat/completions", json=payload,
            headers={"Authorization": f"Bearer {settings.NANOGPT_API_KEY}"},
        )
    resp.raise_for_status()
    data = resp.json()
    return {"answer": extract_answer(data), "model": model, "usage": data.get("usage")}

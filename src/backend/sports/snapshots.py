"""Record a reading of each live game with a market, so analysis (models or people) can read how it moved."""
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Optional

from sqlalchemy import select

from src.backend.database import async_session_factory
from src.backend.models import GameSnapshot
from src.backend.sports.cfb import LiveGame, norm

logger = logging.getLogger(__name__)

_last: dict[tuple[str, str], tuple] = {}  # (league, game id) -> what was last written, to skip repeats

# ESPN box score stat name -> (column suffix, type)
BOX = {"firstDowns": ("first_downs", int), "totalYards": ("total_yards", int), "netPassingYards": ("pass_yards", int),
       "rushingAttempts": ("rush_carries", int), "rushingYards": ("rush_yards", int), "turnovers": ("turnovers", int),
       "thirdDownEff": ("third_down", str), "possessionTime": ("possession_time", str)}


def _num(v: Any, kind: type) -> Any:
    try:
        return kind(v) if kind is str else int(float(v))
    except (TypeError, ValueError):
        return None


def build_row(game: LiveGame, summary: dict, prices: dict[str, float], home_wp: Optional[float], slug: str, league: str,
              baselines: dict[str, Optional[tuple[float, int]]]) -> dict[str, Any]:
    """Column values for one game reading. ``baselines`` maps team id -> (yards per carry allowed, games) when known."""
    def price(team):
        return next((v for k, v in prices.items() if norm(k) in norm(team.name) or norm(team.name) in norm(k)), None)

    row: dict[str, Any] = {
        "league": league, "game_id": game.event_id, "market_slug": slug, "detail": game.detail, "period": game.period,
        "seconds_left": game.seconds_left, "possession": game.possession,
        "home_team": game.home.name, "away_team": game.away.name, "home_rank": game.home.rank, "away_rank": game.away.rank,
        "home_score": game.home.score, "away_score": game.away.score, "home_price": price(game.home),
        "away_price": price(game.away), "home_win_prob": home_wp,
    }
    extra: dict[str, dict[str, str]] = {"home": {}, "away": {}}
    for t in (summary.get("boxscore") or {}).get("teams") or []:
        side = t.get("homeAway")
        if side not in extra:
            continue
        for st in t.get("statistics") or []:
            name, val = st.get("name"), st.get("displayValue")
            if name in BOX:
                col, kind = BOX[name]
                row[f"{side}_{col}"] = _num(val, kind)
            else:
                extra[side][name] = val
    # own defense's baseline on its own side
    for side, team in (("home", game.home), ("away", game.away)):
        base = baselines.get(team.team_id)
        row[f"{side}_ypc_allowed"] = round(base[0], 3) if base else None
    row["box_json"] = json.dumps(extra)
    return row


def changed(key: tuple[str, str], row: dict[str, Any]) -> bool:
    """True when the score, clock, ball or prices moved since the last reading of this game."""
    state = (row["home_score"], row["away_score"], row["period"], int((row["seconds_left"] or 0) // 15), row["possession"],
             round(row["home_price"] or 0, 2), round(row["away_price"] or 0, 2), row.get("home_rush_carries"), row.get("away_rush_carries"))
    if _last.get(key) == state:
        return False
    _last[key] = state
    return True


async def record(rows: list[dict[str, Any]]) -> int:
    """Write the readings that changed. A failure here is logged and never stops alerting."""
    fresh = [r for r in rows if changed((r["league"], r["game_id"]), r)]
    if not fresh:
        return 0
    try:
        async with async_session_factory() as session:
            session.add_all(GameSnapshot(**r) for r in fresh)
            await session.commit()
    except Exception as e:
        logger.warning(f"Could not record game snapshots: {e}")
        return 0
    return len(fresh)


async def purge(days: int = 30) -> None:
    """Drop readings older than ``days``."""
    from sqlalchemy import delete
    async with async_session_factory() as session:
        await session.execute(delete(GameSnapshot).where(GameSnapshot.created_at < datetime.utcnow() - timedelta(days=days)))
        await session.commit()

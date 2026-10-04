"""
What an MLB team looked like going into a game: recent form and starting pitchers.

Used to review the trader's picks. Everything is computed as of the day before the game,
so nothing leaks the result. Pure functions over a list of finished games, plus thin
fetchers for the MLB Stats API.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Optional

import httpx

MLB_API = "https://statsapi.mlb.com/api/v1"


@dataclass(frozen=True)
class Game:
    day: str  # official date, YYYY-MM-DD
    away: str
    home: str
    away_runs: int
    home_runs: int

    @property
    def winner(self) -> str:
        return self.away if self.away_runs > self.home_runs else self.home


@dataclass(frozen=True)
class Form:
    wins: int
    losses: int
    runs_for: float  # per game
    runs_against: float  # per game
    games: int


def team_form(games: list[Game], team: str, before: str, n: int) -> Optional[Form]:
    """Record and run rates over the team's last ``n`` finished games before the date."""
    mine = sorted(
        (g for g in games if g.day < before and team in (g.away, g.home)),
        key=lambda g: g.day,
    )[-n:]
    if not mine:
        return None
    wins = sum(1 for g in mine if g.winner == team)
    rf = sum(g.away_runs if g.away == team else g.home_runs for g in mine)
    ra = sum(g.home_runs if g.away == team else g.away_runs for g in mine)
    return Form(wins, len(mine) - wins, rf / len(mine), ra / len(mine), len(mine))


def parse_games(schedule: dict[str, Any]) -> list[Game]:
    """Finished games from a Stats API schedule payload."""
    games = []
    for day in schedule.get("dates", []):
        for g in day["games"]:
            if g["status"]["abstractGameState"] != "Final":
                continue
            away, home = g["teams"]["away"], g["teams"]["home"]
            if away.get("score") is None or home.get("score") is None:
                continue
            games.append(Game(
                day=g["officialDate"], away=away["team"]["name"], home=home["team"]["name"],
                away_runs=int(away["score"]), home_runs=int(home["score"]),
            ))
    return games


def day_before(day: str) -> str:
    return (date.fromisoformat(day) - timedelta(days=1)).isoformat()


async def fetch_season_games(client: httpx.AsyncClient, start: str, end: str) -> list[Game]:
    resp = await client.get(
        f"{MLB_API}/schedule",
        params={"sportId": 1, "startDate": start, "endDate": end, "gameType": "R"},
    )
    resp.raise_for_status()
    return parse_games(resp.json())


async def fetch_probable_starters(client: httpx.AsyncClient, day: str) -> dict[tuple[str, str], dict[str, Any]]:
    """Starters listed for each game on a date: {(away, home): {'away': (id, name), 'home': (id, name)}}."""
    resp = await client.get(
        f"{MLB_API}/schedule", params={"sportId": 1, "date": day, "hydrate": "probablePitcher,team"}
    )
    resp.raise_for_status()
    out: dict[tuple[str, str], dict[str, Any]] = {}
    for d in resp.json().get("dates", []):
        for g in d["games"]:
            away, home = g["teams"]["away"], g["teams"]["home"]
            pitchers = {}
            for side, t in (("away", away), ("home", home)):
                p = t.get("probablePitcher")
                pitchers[side] = (p["id"], p["fullName"]) if p else None
            out[(away["team"]["name"], home["team"]["name"])] = pitchers
    return out


async def fetch_pitcher_era(client: httpx.AsyncClient, pitcher_id: int, before: str, season_start: str) -> Optional[float]:
    """Season ERA up to (not including) the date."""
    resp = await client.get(
        f"{MLB_API}/people/{pitcher_id}/stats",
        params={"stats": "byDateRange", "group": "pitching", "startDate": season_start, "endDate": day_before(before)},
    )
    resp.raise_for_status()
    splits = (resp.json().get("stats") or [{}])[0].get("splits") or []
    if not splits:
        return None
    try:
        return float(splits[0]["stat"]["era"])
    except (KeyError, ValueError):
        return None

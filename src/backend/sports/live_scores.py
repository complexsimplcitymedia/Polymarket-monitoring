"""
Live scores for the games behind open positions.

Pulls today's scoreboards (college football, NFL, MLB), then matches each leg of an open
position to its game by team names in the leg's title. Read-only; scoreboards are cached
for 30 seconds so the account page can refresh often without hammering the sources.
"""

import asyncio
import re
import time
from datetime import date, datetime, timedelta
from typing import Any, Optional

import httpx

ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports"
ESPN = f"{ESPN_BASE}/football"
MLB = "https://statsapi.mlb.com/api/v1/schedule"
CACHE_SECONDS = 30

_cache: Optional[tuple[float, list[dict[str, Any]]]] = None
_lock = asyncio.Lock()


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", text.lower())).strip()


def team_tokens(*names: Optional[str]) -> set[str]:
    """Names a title might use for a team (location, nickname, full name), normalized."""
    return {norm(n) for n in names if n and len(norm(n)) >= 3}


def _espn_games(payload: dict[str, Any]) -> list[dict[str, Any]]:
    games = []
    for ev in payload.get("events", []):
        comp = ev["competitions"][0]
        sides = {}
        for c in comp["competitors"]:
            t = c["team"]
            sides[c["homeAway"]] = {
                "name": t.get("displayName", ""),
                "tokens": team_tokens(t.get("location"), t.get("name"), t.get("displayName")),
                "score": int(float(c.get("score") or 0)),
            }
        if len(sides) == 2:
            st = comp["status"]["type"]
            games.append({"away": sides["away"], "home": sides["home"], "state": st["state"],
                          "detail": st.get("shortDetail", ""), "start": ev.get("date")})
    return games


def _mlb_games(payload: dict[str, Any]) -> list[dict[str, Any]]:
    games = []
    for d in payload.get("dates", []):
        for g in d["games"]:
            sides = {}
            for key in ("away", "home"):
                t = g["teams"][key]["team"]
                sides[key] = {
                    "name": t["name"],
                    "tokens": team_tokens(t.get("locationName"), t.get("teamName"), t["name"]),
                    "score": int(g["teams"][key].get("score") or 0),
                }
            ls = g.get("linescore", {})
            state = {"Preview": "pre", "Live": "in", "Final": "post"}.get(g["status"]["abstractGameState"], "pre")
            inning = f"{ls.get('inningState', '')} {ls.get('currentInningOrdinal', '')}".strip()
            games.append({"away": sides["away"], "home": sides["home"], "state": state,
                          "detail": inning if state == "in" else g["status"]["detailedState"], "start": g.get("gameDate")})
    return games


async def fetch_scoreboards() -> list[dict[str, Any]]:
    """Every game on today's boards, cached briefly."""
    global _cache
    async with _lock:
        if _cache and time.monotonic() - _cache[0] < CACHE_SECONDS:
            return _cache[1]
        today = date.today()
        async with httpx.AsyncClient(timeout=15.0, headers={"User-Agent": "Mozilla/5.0"}) as client:
            urls = [
                (f"{ESPN}/college-football/scoreboard", {"groups": "80", "limit": 200}, _espn_games),
                (f"{ESPN}/college-football/scoreboard", {"groups": "81", "limit": 200}, _espn_games),
                (f"{ESPN}/nfl/scoreboard", {}, _espn_games),
                (f"{ESPN_BASE}/basketball/nba/scoreboard", {}, _espn_games),
                (f"{ESPN_BASE}/baseball/mlb/scoreboard", {}, _espn_games),
                (MLB, {"sportId": 1, "startDate": (today - timedelta(days=1)).isoformat(),
                       "endDate": (today + timedelta(days=2)).isoformat(), "hydrate": "team,linescore"}, _mlb_games),
            ]
            results = await asyncio.gather(*[client.get(u, params=p) for u, p, _ in urls], return_exceptions=True)
        games: list[dict[str, Any]] = []
        for (_, _, parse), r in zip(urls, results):
            if isinstance(r, Exception) or r.status_code != 200:
                continue
            try:
                games += parse(r.json())
            except (KeyError, ValueError, TypeError):
                continue
        _cache = (time.monotonic(), games)
        return games


def _epoch(iso: Optional[str]) -> Optional[float]:
    if not iso:
        return None
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def match_game(title: str, games: list[dict[str, Any]], start: Optional[str] = None) -> Optional[dict[str, Any]]:
    """The game whose two teams both appear in the leg's title.

    A series has several games between the same teams, so when the leg's start time is known the
    game closest to it wins; otherwise live games come first, then upcoming, then finished.
    """
    t = f" {norm(title)} "
    hits = [g for g in games if any(f" {x} " in t for x in g["away"]["tokens"]) and any(f" {x} " in t for x in g["home"]["tokens"])]
    target = _epoch(start)
    if target is not None and any(_epoch(g.get("start")) is not None for g in hits):
        hits.sort(key=lambda g: abs((_epoch(g.get("start")) or 0) - target))
    else:
        hits.sort(key=lambda g: {"in": 0, "pre": 1, "post": 2}.get(g["state"], 3))
    return hits[0] if hits else None


def line_from_slug(slug: str) -> Optional[float]:
    """The total line from a slug like '...-total-8pt5' or 'tsc-mlb-phi-atl-2026-09-30-7pt5'."""
    m = re.search(r"(\d+)pt(\d)", slug or "")
    return float(f"{m.group(1)}.{m.group(2)}") if m else None


def describe(leg: dict[str, Any], game: dict[str, Any]) -> dict[str, Any]:
    """The score, status, and whether the leg's pick is leading, trailing or tied."""
    away, home = game["away"], game["home"]
    out: dict[str, Any] = {
        "away": away["name"], "home": home["name"], "away_score": away["score"], "home_score": home["score"],
        "state": game["state"], "detail": game["detail"],
    }
    pick = norm(str(leg.get("outcome", "")))
    if pick in ("over", "under"):
        total = away["score"] + home["score"]
        line = line_from_slug(leg.get("slug", ""))
        out.update({"kind": pick, "total": total, "line": line})
        if line is not None:
            out["needs"] = max(int(line - total) + 1, 0) if pick == "over" else None
    else:
        side = next((s for s, g in (("away", away), ("home", home)) if any(f" {x} " in f" {pick} " or x == pick for x in g["tokens"])), None)
        if side:
            mine, theirs = (away, home) if side == "away" else (home, away)
            out["pick"] = mine["name"]
            out["margin"] = mine["score"] - theirs["score"]
            out["status"] = "leading" if out["margin"] > 0 else "trailing" if out["margin"] < 0 else "tied"
    return out


async def attach_live_scores(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Copies of the open positions with a ``live`` block on each leg (or on the position itself)."""
    games = await fetch_scoreboards()
    out = []
    for p in items:
        p = {**p}
        legs = []
        for leg in p.get("legs") or []:
            game = match_game(leg.get("title", ""), games, leg.get("start"))
            legs.append({**leg, "live": describe(leg, game) if game else None})
        p["legs"] = legs
        if not legs and p.get("title"):
            game = match_game(p["title"], games)
            p["live"] = describe({"outcome": p.get("outcome", ""), "slug": p.get("slug", "")}, game) if game else None
        out.append(p)
    return out

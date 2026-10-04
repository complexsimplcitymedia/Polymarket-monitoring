"""Live score lookup for a market, matched by the teams named in its title."""

from typing import Any, Dict, Optional

from fastapi import APIRouter

from src.backend.sports.live_scores import fetch_scoreboards, match_game

router = APIRouter(prefix="/api/scores", tags=["Scores"])


@router.get("/match")
async def match_score(title: str, start: Optional[str] = None) -> Dict[str, Any]:
    """The game whose two teams appear in ``title`` (for example "Kentucky vs. South Carolina"), or null."""
    try:
        game = match_game(title, await fetch_scoreboards(), start)
    except Exception:  # scores are a nicety; never fail the page over them
        game = None
    if not game:
        return {"game": None}
    return {"game": {
        "away": game["away"]["name"], "home": game["home"]["name"],
        "away_score": game["away"]["score"], "home_score": game["home"]["score"],
        "state": game["state"], "detail": game["detail"],
    }}

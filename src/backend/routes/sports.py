"""
Sports momentum scanner routes (MLB, NFL, NBA).

URLs stay under /api/scanners/* for frontend compatibility.
"""

from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException

from src.backend.sports.cfb import DEFAULT_THRESHOLD, scan_live as scan_cfb_live
from src.backend.sports.mlb import (
    get_mlb_momentum_board,
    get_team_momentum_deep_dive as get_mlb_team_deep_dive,
)
from src.backend.sports.nba import (
    get_nba_momentum_board,
    get_team_momentum_deep_dive as get_nba_team_deep_dive,
)
from src.backend.sports.nfl import (
    get_nfl_momentum_board,
    get_team_momentum_deep_dive as get_nfl_team_deep_dive,
)

router = APIRouter(prefix="/api/scanners", tags=["Sports"])


@router.get("/mlb/board")
async def get_mlb_board(season: Optional[int] = None) -> Dict[str, Any]:
    """
    Get all 30 MLB teams ranked by recency momentum (rolling 3-5 game BA,
    active streaks, run differential) vs. season standings.
    Surfaces underdog audition surges and coasting favorite traps.
    Defaults to the current calendar year's season.
    """
    try:
        return await get_mlb_momentum_board(season=season)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"MLB board calculation error: {str(e)}")


@router.get("/mlb/team/{team_id}")
async def get_mlb_team(team_id: int, season: Optional[int] = None) -> Dict[str, Any]:
    """
    Deep-dive recency analysis for a specific MLB team, including game-by-game
    hitting logs, rolling batting average curves, and pre-wire trading guidance.
    Defaults to the current calendar year's season.
    """
    try:
        return await get_mlb_team_deep_dive(team_id=team_id, season=season)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"MLB team deep-dive error: {str(e)}")


@router.get("/nfl/board")
async def get_nfl_board() -> Dict[str, Any]:
    """
    Get all NFL teams ranked by recency momentum (last-3-game scoring
    margin vs. season point differential and streak) vs. season standings.
    Surfaces underdog surges and coasting favorite traps.
    """
    try:
        return await get_nfl_momentum_board()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"NFL board calculation error: {str(e)}")


@router.get("/nfl/team/{team_id}")
async def get_nfl_team(team_id: int) -> Dict[str, Any]:
    """
    Deep-dive recency analysis for a specific NFL team (ESPN team id).
    """
    try:
        return await get_nfl_team_deep_dive(team_id=team_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"NFL team deep-dive error: {str(e)}")


@router.get("/nba/board")
async def get_nba_board() -> Dict[str, Any]:
    """
    Get all NBA teams ranked by recency momentum (last-5-game scoring
    margin vs. season point differential and streak) vs. season standings.
    Surfaces underdog surges and coasting favorite traps.
    """
    try:
        return await get_nba_momentum_board()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"NBA board calculation error: {str(e)}")


@router.get("/nba/team/{team_id}")
async def get_nba_team(team_id: int) -> Dict[str, Any]:
    """
    Deep-dive recency analysis for a specific NBA team (ESPN team id).
    """
    try:
        return await get_nba_team_deep_dive(team_id=team_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"NBA team deep-dive error: {str(e)}")



@router.get("/cfb/live")
async def get_cfb_live(threshold: float = DEFAULT_THRESHOLD) -> Dict[str, Any]:
    """
    Scan live college football (FBS and FCS) for games where the Polymarket price
    lags ESPN's live win probability by at least ``threshold`` (0-1). Flags are also
    saved to the prediction ledger.
    """
    try:
        signals = await scan_cfb_live(threshold=threshold)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"CFB live scan error: {str(e)}")
    return {
        "threshold": threshold,
        "count": len(signals),
        "signals": [
            {
                "event_id": s.game.event_id,
                "game": f"{s.game.away.name} {s.game.away.score} @ {s.game.home.name} {s.game.home.score}",
                "detail": s.game.detail,
                "team": s.team,
                "espn_win_prob": round(s.espn_win_prob, 3),
                "market_price": round(s.market_price, 3),
                "gap": round(s.gap, 3),
                "label_favorite": s.label_favorite,
                "label_basis": s.label_basis,
                "is_label_underdog": s.is_label_underdog,
                "market_slug": s.market_slug,
            }
            for s in signals
        ],
    }

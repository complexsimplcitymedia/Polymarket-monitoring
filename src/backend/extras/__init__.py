"""
Extras: features kept from earlier iterations but isolated from the sports core.

Weather and parlay scanners, the debate floor, and Polymarket trading. Mounted only
when ``settings.ENABLE_EXTRAS`` is true. Nothing in the sports core imports from here.
"""

from fastapi import FastAPI


def include_extras(app: FastAPI) -> None:
    """Mount extras routers on the app."""
    from src.backend.extras.routes import debate, scanners, trading

    app.include_router(debate.router)
    app.include_router(trading.router)
    app.include_router(scanners.router)

"""
Which sports the app covers, and whether each is in season.

Binary predictions only. NBA and college basketball are registered as placeholders until
their seasons start; flip a status to "active" and the rest of the app treats it like the
others. League keys match the platform's own sports list (e.g. "cbb" for college basketball).
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Sport:
    key: str  # league segment in Polymarket US slugs, e.g. "aec-cfb-mich-minnst-2026-10-03"
    name: str
    status: str  # "active" or "offseason"


SPORTS: tuple[Sport, ...] = (
    Sport("mlb", "MLB", "active"),
    Sport("cfb", "College football", "active"),
    Sport("nfl", "NFL", "active"),
    Sport("atp", "ATP tennis", "active"),
    Sport("wta", "WTA tennis", "active"),
    Sport("itfme", "ITF men's tennis", "active"),
    Sport("itfwo", "ITF women's tennis", "active"),
    Sport("nba", "NBA", "active"),  # NBA preseason / regular season active
    Sport("cbb", "College basketball", "offseason"),  # placeholder, not in season yet
)


def active_sports() -> list[Sport]:
    return [s for s in SPORTS if s.status == "active"]


def league_of(slug: str) -> str:
    """League segment of a Polymarket US market slug ('aec-cfb-...' -> 'cfb'), else ''."""
    parts = slug.split("-")
    return parts[1] if len(parts) > 1 else ""


def in_scope(slug: str) -> bool:
    """True if the market belongs to a sport we cover, active or placeholder."""
    return league_of(slug) in {s.key for s in SPORTS}


# Polymarket market slugs start with the league: "cfb-fl-missr-2026-10-03". These are the leagues
# whose markets belong in the market list; esports, soccer, politics and the like are left out.
MARKET_PREFIXES = ("mlb", "cfb", "nfl", "nba", "cbb", "atp", "wta")


def market_prefix(slug: str) -> str:
    return (slug or "").split("-")[0].lower()


def is_sports_market(slug: str) -> bool:
    """True for a market in a league we trade (the ITF tours all start with 'itf')."""
    prefix = market_prefix(slug)
    return prefix in MARKET_PREFIXES or prefix.startswith("itf")

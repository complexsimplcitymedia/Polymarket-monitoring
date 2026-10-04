"""
SQLAlchemy models for the Polymarket News Tracker.

Defines Market, NewsArticle, PriceHistory, and AppState tables with proper indexing.
"""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.backend.database import Base


class Market(Base):
    """Model representing a Polymarket prediction market."""

    __tablename__ = "markets"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    slug: Mapped[str] = mapped_column(String(500), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    volume_24h: Mapped[float] = mapped_column(Float, default=0.0)
    volume_7d: Mapped[float] = mapped_column(Float, default=0.0)
    liquidity: Mapped[float] = mapped_column(Float, default=0.0)
    yes_percentage: Mapped[float] = mapped_column(Float, default=50.0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    end_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    clob_token_ids: Mapped[str | None] = mapped_column(Text, nullable=True)
    # JSON list of {"name", "price"} so a card can show each team and its percentage
    outcomes_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_updated: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("idx_markets_volume_7d", "volume_7d"),
        Index("idx_markets_is_active", "is_active"),
        Index("idx_markets_slug", "slug"),
    )

    def to_dict(self) -> dict:
        """Convert model to dictionary."""
        return {
            "id": self.id,
            "slug": self.slug,
            "title": self.title,
            "description": self.description,
            "volume_24h": self.volume_24h,
            "volume_7d": self.volume_7d,
            "liquidity": self.liquidity,
            "yes_percentage": self.yes_percentage,
            "is_active": self.is_active,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "image_url": self.image_url,
            "clob_token_ids": self.clob_token_ids,
            "last_updated": self.last_updated.isoformat() if self.last_updated else None,
        }


class PriceHistory(Base):
    """Model for storing market price/percentage history over time."""

    __tablename__ = "price_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    market_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    yes_percentage: Mapped[float] = mapped_column(Float, nullable=False)
    volume: Mapped[float] = mapped_column(Float, default=0.0)
    timestamp: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("idx_price_history_market_time", "market_id", "timestamp"),
    )

    def to_dict(self) -> dict:
        """Convert model to dictionary."""
        return {
            "market_id": self.market_id,
            "yes_percentage": self.yes_percentage,
            "volume": self.volume,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }


class NewsArticle(Base):
    """Model representing a news article related to a market."""

    __tablename__ = "news_articles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    market_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    url_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(255), nullable=True)
    author: Mapped[str | None] = mapped_column(String(255), nullable=True)
    image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    sentiment_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("idx_news_market_id", "market_id"),
        Index("idx_news_published_at", "published_at"),
        Index("idx_news_market_published", "market_id", "published_at"),
    )

    def to_dict(self) -> dict:
        """Convert model to dictionary."""
        return {
            "id": self.id,
            "market_id": self.market_id,
            "title": self.title,
            "description": self.description,
            "url": self.url,
            "source": self.source,
            "author": self.author,
            "image_url": self.image_url,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "sentiment_score": self.sentiment_score,
        }


class AppState(Base):
    """Model for storing application state like last update times."""

    __tablename__ = "app_state"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class Opportunity(Base):
    """Model for storing high-conviction detected trading opportunities."""

    __tablename__ = "opportunities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    market_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    bracket: Mapped[str | None] = mapped_column(String(100), nullable=True)
    true_probability: Mapped[float] = mapped_column(Float, default=0.0)
    market_price: Mapped[float] = mapped_column(Float, default=0.0)
    edge: Mapped[float] = mapped_column(Float, default=0.0)
    expected_value_pct: Mapped[float] = mapped_column(Float, default=0.0)
    kelly_fraction_pct: Mapped[float] = mapped_column(Float, default=0.0)
    recommendation: Mapped[str] = mapped_column(String(100), nullable=False)
    target_token_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_side: Mapped[str] = mapped_column(String(10), default="BUY")
    target_limit_price: Mapped[float] = mapped_column(Float, default=0.50)
    status: Mapped[str] = mapped_column(String(50), default="DETECTED")
    details_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("idx_opportunities_created", "created_at"),
        Index("idx_opportunities_status", "status"),
        Index("idx_opportunities_edge", "edge"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "category": self.category,
            "market_id": self.market_id,
            "title": self.title,
            "bracket": self.bracket,
            "true_probability": self.true_probability,
            "market_price": self.market_price,
            "edge": self.edge,
            "expected_value_pct": self.expected_value_pct,
            "kelly_fraction_pct": self.kelly_fraction_pct,
            "recommendation": self.recommendation,
            "target_token_id": self.target_token_id,
            "target_side": self.target_side,
            "target_limit_price": self.target_limit_price,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class HistoricalWeatherRecord(Base):
    """Model for storing 10+ years of historical weather observations per city."""

    __tablename__ = "weather_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    city_key: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    date_str: Mapped[str] = mapped_column(String(10), nullable=False, index=True)  # YYYY-MM-DD
    month_day: Mapped[str] = mapped_column(String(5), nullable=False, index=True)  # MM-DD
    temperature_max: Mapped[float] = mapped_column(Float, nullable=False)
    temperature_min: Mapped[float] = mapped_column(Float, nullable=False)
    precipitation: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("idx_weather_city_mday", "city_key", "month_day"),
        Index("idx_weather_city_date", "city_key", "date_str", unique=True),
    )


class WeatherAnomalyLog(Base):
    """Model for tracking detected atmospheric anomalies and historical analog matches."""

    __tablename__ = "weather_anomalies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    city_key: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    forecast_date: Mapped[str] = mapped_column(String(10), nullable=False)
    forecast_mean: Mapped[float] = mapped_column(Float, nullable=False)
    historical_mean: Mapped[float] = mapped_column(Float, nullable=False)
    historical_std: Mapped[float] = mapped_column(Float, nullable=False)
    z_score: Mapped[float] = mapped_column(Float, nullable=False)
    regime: Mapped[str] = mapped_column(String(50), nullable=False)
    matched_analogs_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())



class Prediction(Base):
    """A binary sports prediction: one yes/no question, one predictor's probability.

    ``predictor`` is who made the call (the user, or a predictor analysing their picks).
    ``probability`` is that predictor's P(yes). ``outcome`` stays NULL until the game
    is settled, then holds 1 (yes) or 0 (no). ``market_price`` is the Polymarket yes
    price (0-1) when the call was made, kept only as a benchmark to beat.
    """

    __tablename__ = "predictions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sport: Mapped[str] = mapped_column(String(20), nullable=False)
    game_id: Mapped[str] = mapped_column(String(100), nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    predictor: Mapped[str] = mapped_column(String(50), nullable=False)
    probability: Mapped[float] = mapped_column(Float, nullable=False)
    market_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    market_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    game_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    outcome: Mapped[int | None] = mapped_column(Integer, nullable=True)
    settled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("predictor", "game_id", "question", name="uq_predictions_pick"),
        Index("idx_predictions_sport_predictor", "sport", "predictor"),
        Index("idx_predictions_outcome", "outcome"),
    )


class BetNote(Base):
    """What the trader says about a bet, kept separate from the bet data pulled from the account.

    ``bet_key`` is ``"<market slug>|<time of the first fill>"``. ``tag`` is "analysis" (the default,
    bets that get shared), "vibe" (a hunch) or "hedge" (added on the side of an existing position). ``why_ended`` records why a bet was closed:
    "bounce" (sold into a price move), "target" (a needed amount was reached), "cut" (a dying leg).
    """

    __tablename__ = "bet_notes"

    bet_key: Mapped[str] = mapped_column(String(300), primary_key=True)
    tag: Mapped[str] = mapped_column(String(20), default="analysis", nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    why_ended: Mapped[str | None] = mapped_column(String(30), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class ProgramTier(Base):
    """The trader's own rating of a team's program, kept next to the season stats.

    ``key`` is ``"<league>:<team id>"`` (for example ``"cfb:25"``). ``tier`` runs from 1 (a weak
    program) to 5 (an elite one) and is NULL when not set. It is a prior to weigh against this
    season's numbers, not a result.
    """

    __tablename__ = "program_tiers"

    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    tier: Mapped[int | None] = mapped_column(Integer, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class Alert(Base):
    """A notification: a team that is ahead but priced below what the game state supports."""

    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    kind: Mapped[str] = mapped_column(String(40), default="underpriced_leader")
    priority: Mapped[str] = mapped_column(String(10), default="normal")  # "normal" or "high"
    sport: Mapped[str] = mapped_column(String(10), nullable=False)
    game_id: Mapped[str] = mapped_column(String(100), nullable=False)
    team: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    espn_win_prob: Mapped[float] = mapped_column(Float, nullable=False)
    market_price: Mapped[float] = mapped_column(Float, nullable=False)
    gap: Mapped[float] = mapped_column(Float, nullable=False)
    margin: Mapped[int] = mapped_column(Integer, default=0)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    market_slug: Mapped[str | None] = mapped_column(String(500), nullable=True)
    delivery: Mapped[str] = mapped_column(String(200), default="in-app only")
    # "active", "retracted" (the lead vanished while the game was still on) or "expired" (the game ended)
    status: Mapped[str] = mapped_column(String(12), default="active", nullable=False)
    retracted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    retract_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (Index("idx_alerts_created", "created_at"), Index("idx_alerts_game_team", "game_id", "team"))


class GameSnapshot(Base):
    """One reading of a live game: score, clock, ball, both sides' box score, market prices and ESPN's win probability.

    Written by the scan whenever something changed, so a model (or a person) can read how a game moved. ``box_json``
    keeps every other box score stat ESPN reported, keyed by side, for anything that has no column.
    """

    __tablename__ = "game_snapshots"
    __table_args__ = (Index("ix_game_snapshots_game_time", "league", "game_id", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)
    league: Mapped[str] = mapped_column(String(10), nullable=False)
    game_id: Mapped[str] = mapped_column(String(40), nullable=False)
    market_slug: Mapped[str | None] = mapped_column(String(200), nullable=True)
    detail: Mapped[str | None] = mapped_column(String(80), nullable=True)
    period: Mapped[int | None] = mapped_column(Integer, nullable=True)
    seconds_left: Mapped[float | None] = mapped_column(Float, nullable=True)
    possession: Mapped[str | None] = mapped_column(String(80), nullable=True)
    home_team: Mapped[str] = mapped_column(String(80), nullable=False)
    away_team: Mapped[str] = mapped_column(String(80), nullable=False)
    home_rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    away_rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    home_score: Mapped[int] = mapped_column(Integer, nullable=False)
    away_score: Mapped[int] = mapped_column(Integer, nullable=False)
    home_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    away_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    home_win_prob: Mapped[float | None] = mapped_column(Float, nullable=True)
    home_first_downs: Mapped[int | None] = mapped_column(Integer, nullable=True)
    home_total_yards: Mapped[int | None] = mapped_column(Integer, nullable=True)
    home_pass_yards: Mapped[int | None] = mapped_column(Integer, nullable=True)
    home_rush_carries: Mapped[int | None] = mapped_column(Integer, nullable=True)
    home_rush_yards: Mapped[int | None] = mapped_column(Integer, nullable=True)
    home_turnovers: Mapped[int | None] = mapped_column(Integer, nullable=True)
    home_third_down: Mapped[str | None] = mapped_column(String(12), nullable=True)
    home_possession_time: Mapped[str | None] = mapped_column(String(10), nullable=True)
    home_ypc_allowed: Mapped[float | None] = mapped_column(Float, nullable=True)  # season rushing yards per carry this defense allows
    away_first_downs: Mapped[int | None] = mapped_column(Integer, nullable=True)
    away_total_yards: Mapped[int | None] = mapped_column(Integer, nullable=True)
    away_pass_yards: Mapped[int | None] = mapped_column(Integer, nullable=True)
    away_rush_carries: Mapped[int | None] = mapped_column(Integer, nullable=True)
    away_rush_yards: Mapped[int | None] = mapped_column(Integer, nullable=True)
    away_turnovers: Mapped[int | None] = mapped_column(Integer, nullable=True)
    away_third_down: Mapped[str | None] = mapped_column(String(12), nullable=True)
    away_possession_time: Mapped[str | None] = mapped_column(String(10), nullable=True)
    away_ypc_allowed: Mapped[float | None] = mapped_column(Float, nullable=True)  # season rushing yards per carry this defense allows
    box_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Polymarket's own event feed, read at the same moment, so the sources can be compared for speed
    poly_score: Mapped[str | None] = mapped_column(String(20), nullable=True)  # "away-home", e.g. "17-13"
    poly_period: Mapped[str | None] = mapped_column(String(10), nullable=True)
    poly_elapsed: Mapped[str | None] = mapped_column(String(10), nullable=True)
    poly_updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # theScore's reading of the same game, for the same comparison
    ts_score: Mapped[str | None] = mapped_column(String(20), nullable=True)  # "away-home"
    ts_clock: Mapped[str | None] = mapped_column(String(20), nullable=True)  # e.g. "4:27 4th"
    ts_updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # NCAA's own scoreboard feed, called directly
    ncaa_score: Mapped[str | None] = mapped_column(String(20), nullable=True)  # "away-home"
    ncaa_clock: Mapped[str | None] = mapped_column(String(30), nullable=True)  # e.g. "4TH 4:40"
    # how long each source took to answer for this reading (ms), to compare network paths
    poly_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    espn_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ts_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)


class MarketTick(Base):
    """One price change on one Polymarket outcome, from the live order-book stream, with exact times.

    Written by the Node ``ticks`` worker. ``source_ts`` is when Polymarket says it happened, ``created_at`` when it was
    stored, and ``lag_ms`` the difference at receipt. ``price`` is the display price (midpoint, or the last trade when
    the spread is wider than 10 cents).
    """

    __tablename__ = "market_ticks"
    __table_args__ = (Index("ix_market_ticks_asset_time", "asset_id", "source_ts"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)
    source_ts: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    asset_id: Mapped[str] = mapped_column(String(90), nullable=False)
    slug: Mapped[str | None] = mapped_column(String(200), nullable=True)
    outcome: Mapped[str | None] = mapped_column(String(80), nullable=True)
    event_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    best_bid: Mapped[float | None] = mapped_column(Float, nullable=True)
    best_ask: Mapped[float | None] = mapped_column(Float, nullable=True)
    price: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_trade: Mapped[float | None] = mapped_column(Float, nullable=True)
    lag_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)


class PriceJump(Base):
    """A sudden move in a Polymarket outcome's price (5+ points inside 5 seconds).

    Market makers react to a play before public score feeds post it, so a jump is a fast signal that something
    happened. ``source_ts`` is when Polymarket stamped the move; compare it with score changes in ``game_snapshots``.
    """

    __tablename__ = "price_jumps"
    __table_args__ = (Index("ix_price_jumps_slug_time", "slug", "source_ts"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)
    source_ts: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    asset_id: Mapped[str] = mapped_column(String(90), nullable=False)
    slug: Mapped[str | None] = mapped_column(String(200), nullable=True)
    outcome: Mapped[str | None] = mapped_column(String(80), nullable=True)
    from_price: Mapped[float] = mapped_column(Float, nullable=False)
    to_price: Mapped[float] = mapped_column(Float, nullable=False)
    delta: Mapped[float] = mapped_column(Float, nullable=False)
    window_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    lag_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)


class SourceProbe(Base):
    """One timed request to one score source, recorded every minute by ``probe.py``.

    ``points_total`` is the sum of points across the games the source calls live; at the same moment, the source with
    more points has seen more of the game. ``cache_age_s`` and ``max_age_s`` come from the response headers.
    """

    __tablename__ = "source_probes"
    __table_args__ = (Index("ix_source_probes_sport_time", "sport", "created_at"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    sport: Mapped[str] = mapped_column(String(10), nullable=False)
    source: Mapped[str] = mapped_column(String(40), nullable=False)
    ok: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cache_age_s: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_age_s: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cdn: Mapped[str | None] = mapped_column(String(30), nullable=True)
    live_games: Mapped[int | None] = mapped_column(Integer, nullable=True)
    points_total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    updated_age_s: Mapped[float | None] = mapped_column(Float, nullable=True)
    error: Mapped[str | None] = mapped_column(String(160), nullable=True)


class GamePlay(Base):
    """One play (football) or pitch (baseball), stored when first seen, with the time it actually happened.

    ``created_at`` is when we first saw it, ``happened_at`` is the source's own timestamp, so the gap is how late
    that source was. The score is the last thing a play changes; this table is the action itself.
    """

    __tablename__ = "game_plays"
    __table_args__ = (
        UniqueConstraint("league", "game_id", "play_id", name="uq_game_plays"),
        Index("ix_game_plays_game_seq", "league", "game_id", "seq"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)
    league: Mapped[str] = mapped_column(String(10), nullable=False)
    game_id: Mapped[str] = mapped_column(String(40), nullable=False)
    play_id: Mapped[str] = mapped_column(String(60), nullable=False)
    seq: Mapped[int] = mapped_column(Integer, default=0)
    period: Mapped[int | None] = mapped_column(Integer, nullable=True)
    clock: Mapped[str | None] = mapped_column(String(40), nullable=True)
    kind: Mapped[str | None] = mapped_column(String(60), nullable=True)
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    happened_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    yards: Mapped[float | None] = mapped_column(Float, nullable=True)  # yards gained, or pitch speed
    scoring: Mapped[bool] = mapped_column(Boolean, default=False)
    turnover: Mapped[bool] = mapped_column(Boolean, default=False)
    home_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    away_score: Mapped[int | None] = mapped_column(Integer, nullable=True)

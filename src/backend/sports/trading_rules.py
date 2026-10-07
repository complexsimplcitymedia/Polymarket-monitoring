#!/home/wolf/miniconda3/envs/messiah/bin/python3
"""
Trading Rules & Fanbase Factor Matrix for Wolf Logic Sports Prediction Markets.

THE FOUNDATIONAL TRADING LAW:
1. "We don't bet on the winner, we bet on positions."
2. "Global +80% Take-Profit Discipline Rule (The 1.8x Scale-Out Law)":
   - UNIVERSAL: The exact second a position hits 1.8x (+80% gain, e.g., $5.00 -> $9.00), it SELLS immediately.
   - Captures peak momentum before hitting the 90¢+ resistance ceiling.
   - Zero reliance on final game outcomes.
3. "Underdog vs Mega-Market Matchup Rule (The Dodgers/Yankees Law)":
   - When playing against a Tier 1 Mega-Market (Dodgers, Yankees), massive retail dip-buying
     constantly absorbs underdog price spikes and forces rapid downward pressure.
   - Never wait for the final win. Against Tier 1 teams, lock in fast +25% to +50% scalps on spikes.
4. "Dip-Averaging Logic":
   - If initial buy entry was at X (e.g. 13¢) and the team demonstrates live offensive momentum
     (threatening bases, scoring runs), any subsequent dip BELOW original entry (e.g. 12¢) is an
     immediate high-value add to lower cost basis and increase rally leverage.
5. "Pregame Underpriced Away-Team First-Strike Rule":
   - Away teams ALWAYS bat first in the Top of the 1st inning.
   - When an away team (e.g., Milwaukee @ 45%) is underpriced pregame, buying before the first pitch
     gives an asymmetric "First-Strike" window.
   - If they score in the Top of the 1st, price surges immediately from 45% -> 65%-75% (+20-30% instant profit).
   - If scoreless (0-0 after 0.5 inning), downside is minimal (~45% -> 43%), giving an 8:1 risk/reward.
6. "Micro-Stake High-Multiplier Asymmetry Rule (The 20x+ / Sub-$3 Ride Law)":
   - When holding a micro-position (Stake <= $3.00) with a 20x+ multiplier potential (Implied Price <= 5¢,
     e.g., paying out $60-$80+ on a late-inning walk-off/rally):
   - NEVER PANIC SELL TO SALVAGE CENTS.
   - Downside is capped at a negligible $3.00, while the upside is $60-$80.
   - The mathematical expected value (+EV) demands letting micro-stake 20x moonshots ride to resolution.
7. "Bottom-9th Home Walk-Off Asymmetry Trigger (The $2 / Sub-10% Law)":
   - Game State: Bottom of the 9th inning (or extras), home team trailing by <= 2 runs or tied.
   - Market Price: Home team priced < 10% (e.g. 5¢ - 8¢).
   - Automated Execution: Fire an automatic $2.00 buy order.
   - Math & +EV: An 18x payout ($36 on $2) only needs to hit 1 out of 18 times (5.5%) to break even.
     Because MLB home teams in the 9th mount walk-off comebacks ~10%-14% of the time, this is
     pure, compoundable positive expected value (+EV).
"""

from dataclasses import dataclass
from typing import Dict, Optional

# Master toggle for live automated enforcement (currently inactive until user deploys)
GLOBAL_DOUBLE_UP_ENABLED = False
DEFAULT_GLOBAL_TP_MULTIPLIER = 1.80  # +80% gain (e.g., $5.00 -> $9.00, 45¢ -> 81¢)
MEGA_MARKET_QUICK_SCALP_MULTIPLIER = 1.25  # +25% quick scalp when facing Tier 1 fanbases
MOONSHOT_MAX_STAKE = 3.00  # Max stake for moonshot ride rule ($3.00)
MOONSHOT_MIN_MULTIPLIER = 20.0  # 20x minimum payout potential to trigger mandatory ride rule

# Bottom-9th Walk-off Trigger Constants
BOTTOM_9TH_MAX_PRICE = 0.10  # Priced below 10%
BOTTOM_9TH_STAKE = 2.00  # $2.00 automatic entry
BOTTOM_9TH_MAX_DEFICIT = 2  # Down by 2 runs or fewer





@dataclass(frozen=True)
class FanbaseTier:
    tier: int
    name: str
    retail_bias_weight: float  # Multiplier for dip-buying speed & retail counter-pressure
    mean_reversion_speed: str  # "hyper-fast", "fast", "moderate", "slow"
    recommended_tp_mult: float  # Take-profit multiple recommendation (e.g. 1.25x - 2.0x)


FANBASE_TIERS: Dict[int, FanbaseTier] = {
    1: FanbaseTier(
        tier=1,
        name="Mega Market / Global Following (Dodgers, Yankees)",
        retail_bias_weight=1.50,
        mean_reversion_speed="hyper-fast",
        recommended_tp_mult=1.25,  # Take quick +25% to +50% scalps on spikes; retail absorbs rallies fast
    ),
    2: FanbaseTier(
        tier=2,
        name="Major Market / High Engagement",
        retail_bias_weight=1.20,
        mean_reversion_speed="fast",
        recommended_tp_mult=2.0,
    ),

    3: FanbaseTier(
        tier=3,
        name="Mid Market / Standard Engagement",
        retail_bias_weight=1.00,
        mean_reversion_speed="moderate",
        recommended_tp_mult=2.25,
    ),
    4: FanbaseTier(
        tier=4,
        name="Small Market / Low Retail Liquidity",
        retail_bias_weight=0.80,
        mean_reversion_speed="slow",
        recommended_tp_mult=2.5,
    ),
}

# Team-to-Fanbase Tier mapping across MLB, NBA, NFL
MLB_FANBASE_TIERS: Dict[str, int] = {
    # Tier 1: Mega Markets (Aggressive retail dip-buyers)
    "Dodgers": 1,
    "Los Angeles Dodgers": 1,
    "LAD": 1,
    "Yankees": 1,
    "New York Yankees": 1,
    "NYY": 1,
    "Red Sox": 1,
    "Boston Red Sox": 1,
    "BOS": 1,
    "Cubs": 1,
    "Chicago Cubs": 1,
    "CHC": 1,
    # Tier 2: Major Markets
    "Braves": 2,
    "Atlanta Braves": 2,
    "ATL": 2,
    "Phillies": 2,
    "Philadelphia Phillies": 2,
    "PHI": 2,
    "Mets": 2,
    "New York Mets": 2,
    "NYM": 2,
    "Astros": 2,
    "Houston Astros": 2,
    "HOU": 2,
    "Giants": 2,
    "San Francisco Giants": 2,
    "SF": 2,
    "Cardinals": 2,
    "St. Louis Cardinals": 2,
    "STL": 2,
    "Blue Jays": 2,
    "Toronto Blue Jays": 2,
    "TOR": 2,
    "Padres": 2,
    "San Diego Padres": 2,
    "SD": 2,
    # Tier 3: Mid Markets
    "Guardians": 3,
    "Cleveland Guardians": 3,
    "CLE": 3,
    "Orioles": 3,
    "Baltimore Orioles": 3,
    "BAL": 3,
    "Mariners": 3,
    "Seattle Mariners": 3,
    "SEA": 3,
    "Rangers": 3,
    "Texas Rangers": 3,
    "TEX": 3,
    "Twins": 3,
    "Minnesota Twins": 3,
    "MIN": 3,
    "Brewers": 3,
    "Milwaukee Brewers": 3,
    "MIL": 3,
    "Diamondbacks": 3,
    "Arizona Diamondbacks": 3,
    "ARI": 3,
    "Tigers": 3,
    "Detroit Tigers": 3,
    "DET": 3,
    "Reds": 3,
    "Cincinnati Reds": 3,
    "CIN": 3,
    "Angels": 3,
    "Los Angeles Angels": 3,
    "LAA": 3,
    "White Sox": 3,
    "Chicago White Sox": 3,
    "CWS": 3,
    "Rockies": 3,
    "Colorado Rockies": 3,
    "COL": 3,
    "Nationals": 3,
    "Washington Nationals": 3,
    "WSH": 3,
    "Pirates": 3,
    "Pittsburgh Pirates": 3,
    "PIT": 3,
    "Royals": 3,
    "Kansas City Royals": 3,
    "KC": 3,
    # Tier 4: Small Markets
    "Rays": 4,
    "Tampa Bay Rays": 4,
    "TB": 4,
    "Athletics": 4,
    "Oakland Athletics": 4,
    "OAK": 4,
    "Marlins": 4,
    "Miami Marlins": 4,
    "MIA": 4,
}


@dataclass
class PositionTriggerConfig:
    entry_price: float
    target_multiplier: float = 2.0  # Double up (100% gain)
    stop_loss_pct: Optional[float] = None
    opponent_team: Optional[str] = None

    @property
    def take_profit_price(self) -> float:
        """The price at which to immediately take profit (e.g., 0.13 * 2.0 = 0.26)."""
        return round(self.entry_price * self.target_multiplier, 4)

    def get_fanbase_tier(self) -> FanbaseTier:
        tier_num = MLB_FANBASE_TIERS.get(self.opponent_team or "", 3)
        return FANBASE_TIERS[tier_num]

    def should_take_profit(self, current_bid: float) -> bool:
        """
        Hot Trigger Condition:
        Returns True if current market bid >= take_profit_price.
        """
        return current_bid >= self.take_profit_price


def should_trigger_bottom_9th_walkoff_lottery(
    inning_num: int,
    half: str,  # "Bottom"
    is_home_team: bool,
    deficit_runs: int,  # e.g., 1 or 2
    current_market_price: float,  # e.g., 0.08
) -> bool:
    """
    Evaluates Rule #7:
    - Inning: Bottom of the 9th (or later / extras)
    - Team: Must be the HOME team (has final walk-off at-bats)
    - Deficit: Trailing by 2 runs or fewer (or tied)
    - Price: Priced below 10% (< 0.10)
    
    Returns True to trigger an automatic $2.00 buy order.
    """
    if inning_num < 9:
        return False
    if half.lower() not in ("bottom", "bot"):
        return False
    if not is_home_team:
        return False
    if deficit_runs > BOTTOM_9TH_MAX_DEFICIT:
        return False
    if current_market_price >= BOTTOM_9TH_MAX_PRICE:
        return False
    return True


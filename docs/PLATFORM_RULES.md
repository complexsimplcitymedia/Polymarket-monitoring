# Platform Rules and Trading System

How the account is actually traded on Polymarket US, as established by the trader from
30 days of live use. These are given facts. The analysis is built around them, not
against them.

## The system

- **Scope: binary predictions only, in MLB, college football, NFL and tennis.** NBA and college
  basketball are placeholders until their seasons start (`sports/registry.py`). Two outcomes, cleanly
  resolved. No soccer (win, draw or lose is three outcomes), no weather, no hockey. Out-of-scope
  code lives in `extras/`.

- **Buy dips, sell the bounce.** Positions are entered after a price drop and closed into
  the rebound. The game outcome does not matter, so settlement win rate and Brier score
  are not meaningful measures here.
- **Micro sizing.** Median entry is $5 and the largest is $10. Bankroll is small today;
  sizing is expected to scale with the bankroll.
- **Stacked combos.** Normal bets are combined into $5 combo (parlay) positions. Combos
  use `caoc-` market slugs, singles use `aec-`, player props use `astatc-`.
- **Ambiguity is a bad prediction.** If any part of a question is left to interpretation,
  it is a poor thing to predict. Its resolution can land somewhere in between (a cancelled
  leg settled at 0.43), and whoever takes a side on a vague question is making a bad
  prediction. Clean, binary, unambiguous markets are preferred.
  Example: a temperature question that names no location or source.
- **Only a definite yes or no.** Anything in between (a push, a partial settlement, a
  cancelled leg paying 0.43) adds unfavorable odds, and in a combo it compounds across the
  legs. Observed: combo legs are almost entirely moneylines, and every spread line in the
  resolved combos is a half-point line, which cannot push.
- **No loyalties.** No team, player or sport is favored; only the win matters. A favorite
  player is bet against if the math does not map.
- **Never hedge against yourself.** Hedging is done on the side of the position, not against it.
- **The crowd trades on emotion; the trader leaves it out.** Predictions made on conviction and
  emotion are where the mispricing comes from.
- **The multiplier drives the pick.** A riskier prediction is taken when its multiplier is higher;
  there is no point staking money on something that will not pay meaningfully if it wins.
  The multiplier is capped at roughly 17 to 20x: a 118x payout, say, is not a good prediction.
  Observed: of 8 bets above 20x (Sept 9 to 23), 7 lost, and none has been placed since.
  Past about 1 in 167 (the best any-order Daily 3 odds) is lottery territory, and chasing it is
  delusional. The only bet at that level was a 187x combo on Sept 19, which lost.
- **Small longshots are fine in moderation.** A stake under $5 that could pay three figures is
  always a good bet, as long as it is not done too much: you only get lucky once in a while.
- **Trends are weights, not rules.** A pattern the trader has noticed (for example, results with
  or against California teams) is a data point that weighs on a decision to an extent. It is
  never followed blindly.
- **Some exits are goal-driven, not price-driven.** A position can be cashed out early because a
  needed dollar amount (for example, a bill) has already been reached; once it is, no more risk is
  taken for a little extra. Those sells are not read as a judgment on the bet.
- **Vibe bets are tagged and kept apart.** Analysis bets are the ones shared with the family; a vibe
  bet is a hunch that is not shared. Every bet is analysis unless marked vibe, so the two can be
  compared. Tags, notes and why a bet ended live in the `bet_notes` table.
- **Not gambling.** Buying low and selling high before the result is trading. Holding to
  see the winner is what gamblers do.

## Account mechanics

- **Cash is debited before bonus credit.** While bonus money is in the account, real cash
  should not be left in it. The balance therefore sits at bonus credit with $0 cash, and
  winnings are withdrawn as they come.
- **Deposit-match loop.** Withdraw winnings, redeposit them, collect the match. The
  redeposited money is winnings, not new capital: real new money in was $10.
- **Bonus is released by trading.** Incentive credit unlocks as positions execute. The
  incentive ledger describes each release against the buy that triggered it, and the
  balance fields show the part still held (`bonusHold`).
- **Bonus types lock differently.** Referral credits earned from friends and credits earned
  from deposit matches follow different locking rules. The incentive ledger tags them
  (`REFERRAL` versus `PROMOTION_DEPOSIT_BONUS`) and the report keeps them separate.
- **Matched bonuses become real money the moment they are bet.** Once a matched credit
  is staked it is withdrawable like cash.
- **Referral credits are mostly held back.** Credits earned from friends are generally not
  made available unless the balance is over $100. The exact rule is still being worked out
  by the trader (open question below).
- **Available to bet is not value.** `buyingPower` / `currentBalance` is bonus credit that
  is not withdrawable. Open positions are held outside it and must be added back.

## Data sources

- **Live scores: MLB comes first from MLB's own data (mlb.com, the MLB Stats API). College football comes from ESPN.** Those are the fastest feeds, so use them. The NFL also uses ESPN.
- **Polymarket's own event feed is the slowest and must not be used for scores or alerts.** On the
  Temple game it was minutes behind ESPN. Polymarket is for prices and the account only.
- Even the fast feeds can lag the broadcast by a minute or more and can post a score that is later
  reversed, so alerts wait about 45 seconds and are retracted if the lead disappears.

## Settlement and costs

- **Cancelled leg in a combo.** A cancelled game does not void the combo or drop the leg.
  The leg settles at a partial price (observed: 0.43) and the combo pays the product of
  its legs' settlement prices. Learned from a three-leg parlay (Sept 27) that paid out
  after one game was cancelled.
- **Fees.** Commission is charged on every fill, about 1 to 1.7 cents per contract, roughly
  5 percent of a 15 cent entry. A round trip pays it twice.
- **Makers are paid, takers pay.** Observed on the account's own fills: the taker commission
  averages about 0.86 cents per contract, while the resting (maker) side received a rebate
  of about 0.16 cents on 192 of 211 fills. Resting orders hit were large (median 102
  contracts, up to 1.5 million) and mostly good-till-cancel or good-till-date.
- **A combo's mark is not its cash-out.** The platform's marked value can be well above what a sale
  returns. Observed Oct 3: a combo marked at $8.95 showed a cash-out of $5.34. Plan on the sell
  screen's number, not the mark.
- **Cost includes the fee.** Price paid per contract is cost divided by quantity. The
  `price` field on a short-side fill is the other team's price, not what was paid.

## Reading the activity feed

- `BUY_LONG` / `BUY_SHORT` open a position; `SELL_LONG` / `SELL_SHORT` close one. A fill
  on the SELL side with `BUY_SHORT` intent is an entry on the opposing outcome.
- Gain is measured from cash flows: net cash out, plus bonus balance, plus open positions
  at mark, minus bonuses credited. See `cash_summary` in
  `src/backend/sports/trader.py`.

## Open questions (trader is still working these out)

- **When do referral credits become withdrawable?** Working model (trader's): the referral
  credit is a reserve the balance must cover. Losing $10 from $100 leaves $90, which does
  not cover it, so nothing is released; only the amount above the reserve can be withdrawn.
  The "$100" seen earlier may be the size of the reserve at the time, not a fixed line.
  Losing referral-funded bets lowers the reserve (the required balance to cover a
  withdrawal), which is why the hold is $77.40 and not the full $100 of referral credit.
  The reserve shrinks as credit releases with trading (`bonusHold` was $77.40 on Oct 3, with
  a balance of $69.06 and `availableToWithdraw` of $0, which fits this model). It also
  accounts for part of the Idaho winnings being withdrawable on Oct 2 to 3.

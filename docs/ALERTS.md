# Alerts: underpriced leaders

Sends a notification when a team is **winning on the scoreboard but the market still prices it
below what the game supports**: the crowd is anchored to the pregame label (rank, brand, spread)
while the game state has moved on.

## When an alert goes out

An **underpriced leader** is a team that is **ahead on the scoreboard while the market still has it
weighted to lose** (priced under 50%). All of these must be true:

1. **A live game** in college football (FBS and FCS) or the NFL, with a matching Polymarket
   moneyline market. Scanned every 60 seconds.
2. **The team is ahead by 5 or more points** (`ALERT_MIN_LEAD`; 5 is the floor and anything above it qualifies). A team that is behind, tied, or up by one or two never alerts.
3. **The market price for that team is under `ALERT_MAX_PRICE`** (default 50%).
4. **Not repeated:** at most one alert per game and team within `ALERT_COOLDOWN_MINUTES`
   (default 30).

An alert is **HIGH** priority when ESPN's live win probability also has the team as a **clear
favorite (60% or more)**, so the model and the scoreboard both disagree with the market.

Each alert records the margin, the market price, ESPN's number, and whether the leader was the
pregame underdog by the spread, rank or record. Real price-versus-game gaps are also written to
the prediction ledger so hit rates can be scored later.

## Second alert: a ranked team is scored on first by an unranked team

A **ranked** team (AP Top 25) is scored on first, and the team that scored first is **unranked**.
The early price dip is the point. It does **not** fire when the first scorer is also ranked, or when
the ranked team scored first.

- College football only (the NFL has no rankings), live games still in the **1st or 2nd quarter**.
- Uses ESPN's first scoring play, so a quick answering score does not hide it.
- Must hold for about 45 seconds (a nullified score cancels it).
- **One alert per game.** Email subject: `[Ranked scored on first] #8 Missouri trailing unranked Florida (priced 62% now)`.
- The email shows the score and clock, the first scoring play, the ranked team's current price, and ESPN's live win probability.

## When an email goes out

The email follows the alert one for one, to keep it simple:

| Event | Email |
|---|---|
| An underpriced alert is raised (the rule above holds for about 45 seconds) | **`[Underpriced] Colorado up 4 but still priced to lose at 29% (ESPN 25%)`**, sent once |
| The same alert is HIGH priority (ESPN also has the team at 60% or better) | Same email, subject starts **`[Underpriced HIGH]`** |
| The team is no longer ahead by 3 while the game is still on | **`[RETRACTED] Colorado is no longer ahead`**, with the new score |
| The same team re-qualifies inside the cooldown (30 minutes) | Nothing: no repeat |
| A ranked team is scored on first by an unranked team (1st or 2nd quarter) | **`[Ranked scored on first] ...`**, once per game |
| The game ends | Nothing |

Each email shows the score and clock, the market price, ESPN's live win probability, the gap, and
whether the leading team was the pregame underdog. Nothing else is emailed yet (no daily summary,
no results).

## Email delivery (Hostinger mailbox over SMTP)

Set these in `.env`, then restart the backend. Leave `SMTP_HOST` or `ALERT_EMAIL_TO` empty and
alerts stay in the app only.

```
SMTP_HOST=smtp.hostinger.com
SMTP_PORT=465
SMTP_USER=<the Hostinger mailbox address>
SMTP_PASSWORD=<that mailbox's password>
SMTP_FROM=<same address>
ALERT_EMAIL_TO=<where alerts should go>
```

Check delivery with `POST /api/alerts/test-email`; it replies with the delivery status.

## Tuning

`ALERT_MAX_PRICE`, `ALERT_MIN_LEAD`, `ALERT_COOLDOWN_MINUTES` and `ALERTS_ENABLED` in `.env`. The 60% high-priority
line is `HIGH_WIN_PROB` in `src/backend/sports/alerts.py`.

## Trailing longshot (college football)

A team down by one score or less (`ALERT_TRAIL_MAX_DEFICIT`, 8) and priced under 30% (`ALERT_TRAIL_MAX_PRICE`) also alerts, subject
`[Longshot]`. It holds while the team is within 8 or ahead, and is retracted if the deficit grows past 8.

## Repeat alerts (nagging)

Inside the 30 minute cooldown a team alerts again if the setup improved since the last alert: 3 or more points further ahead
(or closer, when trailing), or the price down 5 or more points with the margin no worse. Repeats are at least 5 minutes apart.

## Ground game (college football and NFL)

A team with 15 or more carries averaging 5.0 or more yards a carry, while the opponent is under 5.0, raises a `[Ground game]`
alert (once per game and team, after the same 45 second hold). If both teams are at 5.0 or more, or neither, nothing fires.
The yards come from the box score the scan already fetches for matched games, so it adds no requests.

## Context on trailing alerts

- Under a minute left in the 4th and the leading team has the ball: no longshot alert (they can run out the clock).
- A trailing team that gets the ball back (turnover or stop) re-alerts right away, at least a minute after the last one.
- Alerts that are not improving do not repeat; see "Repeat alerts" above.
- The alert text includes who has the ball when ESPN reports it.

## Anomaly: running far above what the defense allows

An offense with 15 or more carries at 5.0+ yards a carry, **and** at least 2.0 above what the defense across from it has
allowed per carry this season (`ANOMALY_GAP` in `sports/cfb.py`), raises an `[Anomaly]` alert. The defense's number is built from its
finished games' box scores (`sports/defense_baseline.py`; ESPN publishes no yards allowed). Each finished game is fetched once and
cached, and a defense is only looked up when the opposing offense is already running well. Needs 3+ games of data. Once per game and team.

# BUILD_NOTES — Tidepool (btc-race-24h-20261112-1439)

## What this entry is

A long-only cbBTC/USDC bot on 1-minute bars, $1,000 paper capital.
It buys the flush itself and sells the bounce into strength — at most
three round trips per 24 h window. Python 3.13, standard library only,
no network, no clock, no randomness, fully deterministic (two
protocol-level runs produce byte-identical action logs).

## The dev window, as measured

- 1,439 bars, BTC $73,739 → $72,044 (−2.33%). Buy-and-hold loses −$25.97
  in the local replay (fees included). One 1-minute gap (bar 977).
- The window has three legs: an early rally to $74,689 (bars 0–420), a
  −1.5% drop with a +0.9% bounce (bars 420–610), and a long quiet grind
  down to $72,044 (bars 720–1439) with one weak late flush at bar 1350.
- Oracle ceiling (perfect foresight, same costs): +$44.72. The best
  achievable 2 round trips: buy fill bar 46 ($73,361) → sell 415
  ($74,678), +1.80%; buy fill 516 ($73,448) → sell 610 ($74,118),
  +0.91%. Total +2.71% gross ≈ +$21.7 net — exactly the #2 entry's
  dev score, which confirms the mechanism.

## Leaderboard (dev, fresh fetch 13 Nov ~00:11 WIB, n = 340 finished)

- Top: #1 +$22.90, #2 +$21.70, #3 +$21.60, #10 +$18.50. Median +$5.97;
  338/340 entries > $0; only 23 entries > $15.
- The crowd is saturated with dip-buy swing bots (4–6 trades, 2–3 round
  trips, TP ~0.7%). No house/baseline rows appear in the dev board.
- Build cost of the top 10: $0.00–$42 (median ~$1.7); #1 cost $0.15.
  Winners win with ~$0 of model spend — this bot's build cost is $0
  and it makes no model calls at runtime (none are allowed to matter:
  the program is deterministic rules, not inference).

## Why Tidepool is different (not a clone of the crowd)

1. **It buys INTO the flush, with no bounce confirmation.** Every
   confirmation filter tested (close up, close near bar high, 3-bar
   momentum) fired mid-fall and then blocked the real entry via
   stop-loss + cooldown. The entry is the oversold extreme itself:
   RSI(14) ≤ 25 with the close ≥ 1.5% below its 240-bar high.
2. **The high it fell from must be RECENT (≤ 120 bars old).** A flush
   off a stale high is just the tail of a long grind, and its bounces
   fail. At bar 515 the high was 100 bars old (trade won +$4.50 net);
   at bar 1351 it was 165 bars old (trade lost −$3.73). The filter
   keeps the bot out of the dead second half entirely: 0 trades, $0.
3. **The opening dip is a separate leg.** In the first 180 bars, a
   shallow dip (0.45% off the 60-bar high, RSI ≤ 45, close in the
   bottom fifth of its Bollinger band) catches the day's first leg,
   which dip-only bots wait out. It fired twice (bars 43, 88) for
   +$10.40 and +$8.67 net.
4. **Depth-weighted sizing.** The notional is scaled by mean 240-bar
   pool depth / current depth, clamped to [0.6, 1.0]. Depth ranges
   $0.94M–$1.58M across the window, so a $1,000 buy's impact varies
   6.3–10.7 bps. No baseline and no visible entrant reads depth.
5. **Exits sell strength, not a clock.** TP +0.9%, trailing stop
   0.35% off the bounce peak, wide −0.9% stop, RSI ≥ 78 exit once up
   ≥ +0.5%, max hold 400 bars. The RSI exit sold both rally tops
   (bars 57, 160). Tight stops were the single biggest leak in v1–v3
   (they fired mid-fall; see "What failed" below).

## Local verification

Replay model (exact per RULES.txt): fill at the next bar's open, fee
4 bps, slippage 2 bps, constant-product impact vs that bar's o_depth,
final flatten at the last close. Two independent implementations agree:
a fast backtester and a protocol-level driver that runs `main.py` as a
subprocess over the real bars-replay/v1 wire (hello → batches → done).

| Check | Result |
|---|---|
| Dev net PnL | **+$22.39** (would rank ~#2 of 340 on dev) |
| Max drawdown | 0.30% (limit 25%) |
| Trades | 6 (3 round trips; min 1 required) |
| Fees paid | $2.43 |
| Net PnL at 2× fees | +$19.95 |
| First half / second half | +$22.39 / $0.00 (no trades) |
| Determinism | 2 runs, byte-identical action logs |
| Trade log (fill bars) | BUY 46 $73,437 → SELL 57 $74,292; BUY 88 $73,961 → SELL 160 $74,595; BUY 514 $73,580 → SELL 556 $73,906 |

## What failed on the way here (and what it taught)

- v1 (fixed 0.45% dip off 60-bar high, TP 0.7%): −$8.20. Bought
  rally pullbacks near the top, then the big drop stopped it out twice.
- v2 (SMA-cross trend ride + 120-min-return dip): −$13.88. The SMA
  cross fired at the top of the rally; the dip trigger fired on the
  bounce, not the low.
- v3 (deep flush vs 240-bar high + bounce confirmation): −$10.76.
  Confirmation is vacuous on these bars (intrabar ranges are ~$0–30)
  and the stop-loss + 60-bar cooldown blocked the winning re-entry.
- Kit baselines in the same replay: buy-and-hold −$25.97, EMA-cross
  −$95.87 (68 whipsaw trades), RSI-Bollinger −$46.52, momentum −$52.27.
  The crowd's edge is not in the baselines; it is in buying the two
  big legs and sitting out the grind.
- Parameter sensitivity (dev PnL): early-dip 0.40% → +$21.18,
  0.45% → +$22.39, 0.35% → +$15.11; early-RSI 45 → +$21.18,
  40 → +$3.66 (too strict — blocks the rally legs), 50 → +$14.61;
  flush 1.5% → +$22.39, 1.2% → +$11.64 (too early), 1.8% → +$17.48;
  hi_age 120/150 → +$22.39, 90 → +$17.48. The chosen point sits on a
  plateau, not a spike — but the early-RSI 45 threshold is the
  sharpest edge and the main thing to watch.

## Risks (honest)

1. **Regime risk (biggest).** The dev window's profit is concentrated
   in two legs (early rally + one V-flush). If the race window is a
   slow grind down with weak bounces (like the dev second half), the
   bot trades little or nothing ($0, fails the ≥1-trade bar) — better
   than losing, but no prize.
2. **The RSI-78 exit is load-bearing.** Both rally sales used it. If
   the race rally tops out below RSI 78, the trailing stop still exits
   (0.35% off peak), for less.
3. **One-window tuning.** All parameters were chosen on the single
   24 h dev window. Mitigations: few parameters, plateau (not spike)
   sensitivity, halves test, 2×-fees test, depth sizing, max 3 RTs.
   Even so, race-window PnL is genuinely uncertain — the dev rank
   (~#2) does not predict the race rank.
4. **Fill-lag risk.** Every entry fills one minute after the signal.
   In a fast crash the fill can be ~0.2% worse than the signal close;
   the wide stop (−0.9%) and the flush depth (≥1.5%) absorb that.

## Backups

- Cadangan: the same bot with `MAX_RT = 2` and `FLUSH = 0.018`
  (+$17.48 dev, only the two rally legs, skips the flush leg) — use
  only if the 3-RT version looks too aggressive on review.
- If the race window opens in a waterfall (no early dip, flushes with
  stale highs), the bot will sit in cash; that is by design.

## Submit plan (NOT executed — needs the user's go-ahead)

1. Repo (already created by the parent agent, public, empty):
   https://github.com/tiVan0/makefun-btc-race-dipbuy
   Push this directory's files (main.py, vendor/, LICENSE, README.md,
   BUILD_NOTES.md) as the first content commit. The repo must be
   created after the competition opened (it was, 13 Nov ~00:31 WIB)
   and carry an OSI-approved license (MIT, included).
2. Bundle the builder session transcripts with the kit CLI
   (`node cli/makefun.mjs bundle`) — bundle ONLY this build's session,
   never the main agent session (it contains unrelated secrets/paths).
3. Submit via the kit CLI before the deadline (13 Nov 03:39 WIB),
   then verify the submission shows `finished` with a dev grade
   PnL > $0 (the dev gate). The local grade is +$22.39, but the
   server grade is the one that counts — check it, do not assume it.
4. If the server grade fails (as Roblox and Pumpfun v2 did on 12 Nov
   with empty scores/runs), do NOT resubmit blindly: diagnose first
   (a separate diagnosis is already running for those two failures).

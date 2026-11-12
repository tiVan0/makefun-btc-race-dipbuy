# Tidepool — cbBTC flush-and-bounce bot

A long-only bot for the make.fun BTC race (`btc-race-24h-20261112-1439`).
It trades Coinbase Wrapped BTC against USDC on 1-minute on-chain bars,
starting from $1,000 of paper money.

## The idea

Buy the flush itself — a deep, oversold dip off a *recent* high — and sell
the bounce into overbought strength. At most three round trips a day.

- **Opening dip** (first 180 bars): the close 0.45% below its 60-bar high,
  RSI(14) ≤ 45, close in the bottom fifth of its Bollinger band.
- **Deep flush** (from bar 240): the close ≥ 1.5% below its 240-bar high,
  that high at most 120 bars old, RSI(14) ≤ 25.
- **Depth-weighted size**: notional × clamp(mean 240-bar depth / current
  depth, 0.6, 1.0). The pool is the only pricing venue, and a $1,000 buy
  moves its own price 6–11 bps depending on depth.
- **Exits**: take profit +0.9%, trailing stop 0.35% off the bounce peak,
  hard stop −0.9%, RSI ≥ 78 exit once up ≥ +0.5%, max hold 400 bars.

## Local result (dev window, all fees)

| | |
|---|---|
| Net PnL | **+$22.39** |
| Max drawdown | 0.30% |
| Trades | 6 (3 round trips) |
| Fees paid | $2.43 |
| At doubled fees | +$19.95 |

First half of the window: +$22.39. Second half: $0 (no trades — the bot
sits out the grind instead of bleeding fees). Two protocol-level runs are
byte-identical (deterministic).

## Files

- `main.py` — the bot (Python 3.13, standard library only, no network,
  no clock, no randomness).
- `vendor/makefun_bars.py` — byte-identical copy of the kit's SDK shim.
- `BUILD_NOTES.md` — strategy, leaderboard analysis, backtests, risks,
  and the submit plan.
- `LICENSE` — MIT.

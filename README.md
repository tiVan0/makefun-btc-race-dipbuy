# makefun-btc-race-dipbuy

[![make.fun · btc-race-24h-20261112-1439](https://make.fun/badge/btc-race-24h-20261112-1439.svg)](https://make.fun/bounty/btc-race-24h-20261112-1439)

Dip-buy swing bot for the make.fun BTC race (`btc-race-24h-20261112-1439`):
it trades Coinbase Wrapped BTC (cbBTC) against USDC, one minute bar at a
time, on $1,000 of paper money. Deterministic, standard library only, no
network, no clock, no model calls.

## Strategy

- **Entry:** buy when the close is at least 35bp below the trailing
  45-bar high, the close bounced (close above the previous close), and the
  close is at or above its 60-bar SMA (uptrend gate; the gate passes while
  fewer than 60 closes exist).
- **Size:** full size (all cash), one open position, long only.
- **Exit:** the whole position at +60bp over cost (fees included) or
  -40bp under cost. One stop-loss ends all further entries (circuit
  breaker). At most 2 round trips per window.
- All arithmetic is exact BigInt math on raw price units, so two runs on
  the same bars produce byte-identical action logs.

## Local grade (dev window, official harness)

```
net PnL   +16.25 USDC (4 trades, win rate 1.00, max drawdown 0.39%)
fees      1.61 USDC; at 2x fees net PnL +14.62 USDC
```

Verified with `node cli/makefun.mjs grade-local --kit . --bot <dir>
--driver process` from the competition kit. The dev gate is net PnL above
$0 after every fee; this bot clears it with margin.

## Run it

```sh
node cli/makefun.mjs grade-local --kit . --bot . --driver process
```

---

<sub>Entered on [make.fun](https://make.fun) · AI agents build software for cash rewards</sub>

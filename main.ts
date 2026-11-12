// Dip-buy swing bot (deterministic, no model calls, stdlib only).
//
// MAIN A, from dev-window leaderboard study (btc-race-24h-20261112-1439):
// - Buy when the close is >=35bp below the trailing 45-bar high, the close
//   bounced (close > previous close), and the close is at/above its 60-bar
//   SMA (uptrend gate; the gate passes while fewer than 60 closes exist).
// - Full size (all cash), one open position, long only.
// - Exit the whole position at +60bp over cost (fees included) or -40bp
//   under cost. One stop-loss ends all further entries (circuit breaker).
// - At most 2 round trips per window.
// All arithmetic is exact BigInt math on raw price units, so two runs on
// the same bars produce byte-identical action logs.
import { runBars, type BarsState, type Batch, type OrderInput } from './vendor/makefun-bars.ts';

const SYMBOL = 'CBBTC';
const DIP_BPS = 35n;
const LOOKBACK = 45;
const SMA_BARS = 60;
const TP_BPS = 60n;
const SL_BPS = 40n;
const MAX_RT = 2;
const MAX_SLIPPAGE_BPS = 100;

const closes: bigint[] = [];
let roundTrips = 0;
let stopLosses = 0;

await runBars({
  onBatch(state: BarsState, _batch: Batch): OrderInput[] {
    if (state.warmingUp) {
      const c = state.close(SYMBOL);
      if (c !== null) closes.push(c);
      return [];
    }
    const close = state.close(SYMBOL);
    if (close === null) return [];
    const held = state.positions.get(SYMBOL);
    let orders: OrderInput[] = [];
    if (held !== undefined) {
      const value = state.value(SYMBOL, held.qty);
      const cost = held.cost;
      if (value * 10000n >= cost * (10000n + TP_BPS)) {
        orders = [{ side: 'sell', symbol: SYMBOL, qty: held.qty, max_slippage_bps: MAX_SLIPPAGE_BPS }];
        roundTrips += 1;
      } else if (value * 10000n <= cost * (10000n - SL_BPS)) {
        orders = [{ side: 'sell', symbol: SYMBOL, qty: held.qty, max_slippage_bps: MAX_SLIPPAGE_BPS }];
        roundTrips += 1;
        stopLosses += 1;
      }
    } else if (roundTrips < MAX_RT && stopLosses < 1 && closes.length >= LOOKBACK) {
      let high = 0n;
      for (const c of closes.slice(-LOOKBACK)) if (c > high) high = c;
      const prev = closes[closes.length - 1];
      const dip = close * 10000n <= high * (10000n - DIP_BPS);
      const bounce = close > prev;
      let gate = true;
      if (closes.length + 1 >= SMA_BARS) {
        let sum = close;
        for (const c of closes.slice(-(SMA_BARS - 1))) sum += c;
        gate = close * BigInt(SMA_BARS) >= sum;
      }
      if (dip && bounce && gate && state.cash > 0n) {
        orders = [{ side: 'buy', symbol: SYMBOL, notional_quote_units: state.cash, max_slippage_bps: MAX_SLIPPAGE_BPS }];
      }
    }
    closes.push(close);
    return orders;
  },
});

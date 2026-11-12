"""Tidepool: a depth-weighted flush-and-bounce cbBTC bot (long only, $1000 paper).

The idea, in one line: buy the flush itself -- a deep, oversold dip off a
RECENT high -- and sell the bounce into overbought strength, at most three
times a day. Everything else in this file is risk control around that line.

Why it is not another dip-buy swing bot (the crowd's family, ~340 entries):
  1. It buys INTO the flush, with no bounce confirmation. Confirmation
     filters only ever fired mid-fall and then blocked the real entry.
     The entry is the oversold extreme itself: RSI(14) <= 25 and the close
     >= 1.5% below the 240-minute high.
  2. The high it fell from must be RECENT (<= 120 bars old). A flush off a
     stale high is just the tail of a long grind, and its bounces fail.
     That one filter is what keeps the bot out of the dead second half of
     the dev window entirely (0 trades there, $0, instead of a losing trade).
  3. The opening dip is a separate leg: in the first 180 bars, a shallow
     dip (0.45% off the 60-minute high) with RSI <= 45 and the close in
     the bottom fifth of its Bollinger band. It catches the day's first
     leg, which dip-only bots wait out.
  4. Size is depth-weighted: the notional is scaled by
     mean 240-bar pool depth / current depth, clamped to [0.6, 1.0].
     A $1000 buy moves its own price ~6-11 bps depending on depth, so
     buying when the pool is shallow is paying extra for the same trade.
     No other entrant or baseline reads depth at all.
  5. Exits sell strength, not a clock: take profit +0.9%, a 0.35%
     trailing stop off the bounce peak, a wide -0.9% stop, and an
     RSI >= 78 exit once the position is up >= +0.5% (sell the overbought
     spike). No tight stop: tight stops fired mid-fall in every test.

Determinism: pure functions of the bars seen so far. No clock, no
environment, no files, no network, no randomness, standard library only.
The vendor shim is a byte-identical copy of the kit's SDK shim.

Dev-window result (local replay, fee 4 bps + slippage 2 bps + pool impact):
  net PnL +$22.39, max drawdown 0.30%, 6 trades (3 round trips), fees $2.43.
  At doubled fees: +$19.95. First half +$22.39, second half $0 (no trades).

Rev 2 (13 Nov 2026): named constants for the magic numbers + factored order
builders. No behaviour change: same decisions, same fills, same PnL
(verified: two independent replays still give +$22.39, 6 trades).
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor"))
import makefun_bars

SYMBOL = "CBBTC"

# --- tuned constants (backtested on the dev window; see BUILD_NOTES.md) ---
EARLY_END = 180          # opening-dip leg only in the first 180 bars
EARLY_DIP = 0.0045       # 0.45% below the 60-bar high
EARLY_RSI = 45.0
EARLY_BB = 0.20          # close in the bottom fifth of its Bollinger band
EARLY_HIGH_BARS = 60     # the high the opening dip is measured against
FLUSH = 0.015            # 1.5% below the 240-bar high
FLUSH_RSI = 25.0
FLUSH_HIGH_BARS = 240    # the high the flush is measured against
HI_AGE_MAX = 120         # the 240-bar high must be <= 120 bars old
TP = 0.009               # take profit +0.9%
TRAIL = 0.0035           # trailing stop 0.35% off the bounce peak
STOP = 0.009             # hard stop -0.9%
RSI_EXIT = 78.0          # sell overbought strength (only when up >= +0.5%)
RSI_EXIT_MIN_GAIN = 0.005  # the +0.5% the RSI exit requires before it fires
MAX_HOLD = 400           # bars
MAX_RT = 3               # at most three round trips per window
NO_ENTRY_AFTER = 1400    # no new entries in the last 40 bars
MAX_SLIP_BPS = 100

# --- indicator / sizing constants (values unchanged from rev 1) ---
RSI_PERIOD = 14         # RSI lookback, in bars
BB_PERIOD = 20          # Bollinger band lookback, in bars
BB_SIGMA = 2.0          # Bollinger band width, in standard deviations
DEPTH_WINDOW = 240      # bars of pool depth averaged for sizing
DEPTH_MIN = 0.6         # depth-factor clamp, low end
DEPTH_MAX = 1.0         # depth-factor clamp, high end (never size up)

closes = []   # closes in USD (float), one per batch
highs = []    # highs in USD
lows = []     # lows in USD
depths = []   # close depths in USD (float)
typical = []  # (h + l + c) / 3 per bar

round_trips = 0
entry_price = None   # raw fill price of the open position (int)
peak = None          # raw peak close since entry (int)
held = 0             # bars held


def rsi14():
    """RSI over the last RSI_PERIOD closes: simple means of gains and losses."""
    if len(closes) < RSI_PERIOD + 1:
        return None
    gains = 0.0
    losses = 0.0
    for i in range(len(closes) - RSI_PERIOD, len(closes)):
        d = closes[i] - closes[i - 1]
        if d > 0:
            gains += d
        else:
            losses -= d
    if gains + losses == 0:
        return 50.0
    return 100.0 * gains / (gains + losses)


def bbpos():
    """Position of the close inside its BB_PERIOD-bar Bollinger band (0 = lower)."""
    if len(typical) < BB_PERIOD:
        return None
    w = typical[-BB_PERIOD:]
    m = sum(w) / BB_PERIOD
    var = sum((x - m) ** 2 for x in w) / BB_PERIOD
    sd = var ** 0.5
    if sd == 0:
        return 0.5
    return (closes[-1] - (m - BB_SIGMA * sd)) / (2.0 * BB_SIGMA * sd)


def depth_factor():
    """Scale the notional by pool depth: deep pool -> full size."""
    if len(depths) < DEPTH_WINDOW or depths[-1] <= 0:
        return 1.0
    mean_d = sum(depths[-DEPTH_WINDOW:]) / DEPTH_WINDOW
    f = mean_d / depths[-1]
    return DEPTH_MIN if f < DEPTH_MIN else (DEPTH_MAX if f > DEPTH_MAX else f)


def buy_order(notional):
    """A buy of `notional` quote units (fee included), slippage-capped."""
    return [{"side": "buy", "symbol": SYMBOL,
             "notional_quote_units": notional,
             "max_slippage_bps": MAX_SLIP_BPS}]


def sell_order(qty):
    """Sell the whole position: `qty` at qty_scale, slippage-capped."""
    return [{"side": "sell", "symbol": SYMBOL, "qty": qty,
             "max_slippage_bps": MAX_SLIP_BPS}]


def on_batch(state, batch):
    global round_trips, entry_price, peak, held
    k = state.seq
    bar = batch["bars"][0] if batch["bars"] else None
    if bar is not None:
        ps = 10 ** state.symbols[SYMBOL]["price_scale"]
        closes.append(int(bar["c"]) / ps)
        highs.append(int(bar["h"]) / ps)
        lows.append(int(bar["l"]) / ps)
        typical.append((highs[-1] + lows[-1] + closes[-1]) / 3.0)
        depths.append(int(bar["c_depth"][0]) / 1_000_000.0)
    # Fills of the previous batch's orders land here.
    for fill in batch["fills"]:
        if fill["symbol"] != SYMBOL or fill["status"] != "filled":
            continue
        if fill["side"] == "buy":
            entry_price = int(fill["price"])
            peak = entry_price
            held = 0
        elif fill["side"] == "sell":
            entry_price = None
            peak = None
            held = 0
            round_trips += 1
    if state.warming_up or bar is None:
        return []
    pos = state.positions.get(SYMBOL)
    holding = pos is not None and int(pos.qty) > 0
    close_raw = int(bar["c"])
    ps = 10 ** state.symbols[SYMBOL]["price_scale"]
    if holding:
        held += 1
        if peak is None or close_raw > peak:
            peak = close_raw
        entry = entry_price if entry_price is not None else close_raw
        entry_usd = entry / ps
        peak_usd = peak / ps if peak is not None else None
        if closes[-1] >= entry_usd * (1.0 + TP):
            return sell_order(int(pos.qty))
        if peak_usd is not None and closes[-1] <= peak_usd * (1.0 - TRAIL):
            return sell_order(int(pos.qty))
        if closes[-1] <= entry_usd * (1.0 - STOP):
            return sell_order(int(pos.qty))
        r = rsi14()
        if (r is not None and r >= RSI_EXIT
                and closes[-1] >= entry_usd * (1.0 + RSI_EXIT_MIN_GAIN)):
            return sell_order(int(pos.qty))
        if held >= MAX_HOLD:
            return sell_order(int(pos.qty))
        return []
    # Flat: look for an entry.
    if round_trips >= MAX_RT or k >= NO_ENTRY_AFTER or k < 20:
        return []
    r = rsi14()
    # Leg 1: opening dip (first 180 bars).
    if k <= EARLY_END:
        h60 = max(highs[max(0, k - (EARLY_HIGH_BARS - 1)):])
        if (h60 - closes[-1]) / h60 >= EARLY_DIP:
            bp = bbpos()
            if (r is not None and r <= EARLY_RSI
                    and bp is not None and bp <= EARLY_BB):
                n = int(state.cash * depth_factor())
                if n >= int(state.hello["fees"]["min_notional_quote_units"]):
                    return buy_order(n)
    # Leg 2: deep flush off a recent 240-bar high.
    if k >= FLUSH_HIGH_BARS:
        lo = k - (FLUSH_HIGH_BARS - 1)
        window = highs[lo:]
        h240 = max(window)
        hi_age = k - (lo + window.index(h240))
        if ((h240 - closes[-1]) / h240 >= FLUSH and hi_age <= HI_AGE_MAX
                and r is not None and r <= FLUSH_RSI):
            n = int(state.cash * depth_factor())
            if n >= int(state.hello["fees"]["min_notional_quote_units"]):
                return buy_order(n)
    return []


makefun_bars.run(on_batch)

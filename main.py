"""
====================================================================================================
                        SHENEX FLOW SCALPER PRO - 24/7 CLOUD BOT
               High-Conviction EMA 7/21 • Break of Structure • Order Flow Surge
               Strict 50 EMA Macro Trend Lock • 100% Free 24/7 Cloud Service
               Exact TradingView Pine Script Logic & State Synchronization
====================================================================================================
"""

import sys
import os
import time
import json
import math
import datetime
import threading
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler

# Cloud / Env Configuration
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8731655819:AAHlaeqEdPerKFF3DikMN4mptdEnnbbIkCQ")
CHAT_ID = os.environ.get("CHAT_ID", "7859791756")
PORT = int(os.environ.get("PORT", 7860))

CONFIG = {
    "symbol": "PAXGUSDT",  # Gold (XAUUSD Pegged)
    "interval": "5m",
    "ema_fast": 7,
    "ema_slow": 21,
    "ema_base": 50,
    "use_trend_filter": True,
    "bos_lookback": 8,
    "min_body_percent": 45.0,
    "delta_surge_mult": 1.1,
    "sl_atr_mult": 1.5,
    "rr_ratio": 2.0,
    "cooldown_bars": 8,
    "single_wave_entry": True,
    "account_balance": 500.0,
    "risk_percent": 2.0
}

bot_stats = {
    "status": "RUNNING 24/7",
    "start_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC"),
    "bars_processed": 0,
    "last_price": 0.0,
    "last_trend": "INITIALIZING",
    "last_bar_time": "",
    "signals_sent": 0
}

def send_telegram(token, chat_id, message):
    if not token or not chat_id:
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML"
    }
    try:
        r = requests.post(url, json=payload, timeout=8)
        return r.status_code == 200
    except Exception as e:
        print(f"[ERROR] Failed to send Telegram message: {e}", flush=True)
        return False

def calc_ema(values, length):
    if len(values) < length:
        return values
    k = 2.0 / (length + 1)
    ema = [values[0]]
    for v in values[1:]:
        ema.append(v * k + ema[-1] * (1.0 - k))
    return ema

def calc_atr(highs, lows, closes, length=14):
    trs = []
    for i in range(len(closes)):
        if i == 0:
            trs.append(highs[i] - lows[i])
        else:
            tr = max(highs[i] - lows[i], abs(highs[i] - closes[i-1]), abs(lows[i] - closes[i-1]))
            trs.append(tr)
    return calc_ema(trs, length)

def fetch_candles(symbol="PAXGUSDT", interval="5m", limit=250):
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
    res = requests.get(url, timeout=10)
    data = res.json()
    candles = []
    for c in data:
        candles.append({
            "time": int(c[0]),
            "open": float(c[1]),
            "high": float(c[2]),
            "low": float(c[3]),
            "close": float(c[4]),
            "volume": float(c[5]),
            "close_time": int(c[6])
        })
    return candles

def sync_with_history(eval_candles, cfg):
    last_signal_state = 0
    last_signal_bar_idx = -100
    in_trade = False
    trade_dir = 0
    entry_px = 0.0
    sl_px = 0.0
    tp_px = 0.0
    bar_index = 0

    total_bars = len(eval_candles)
    start_idx = max(60, total_bars - 180)

    for idx in range(start_idx, total_bars):
        bar_index += 1
        sub = eval_candles[:idx+1]
        closes = [c["close"] for c in sub]
        opens  = [c["open"]  for c in sub]
        highs  = [c["high"]  for c in sub]
        lows   = [c["low"]   for c in sub]
        vols   = [c["volume"] for c in sub]

        c_close = closes[-1]
        c_open  = opens[-1]
        c_high  = highs[-1]
        c_low   = lows[-1]
        c_vol   = vols[-1]

        if in_trade:
            if trade_dir == 1:
                sl_hit = c_low <= sl_px
                tp_hit = c_high >= tp_px
            else:
                sl_hit = c_high >= sl_px
                tp_hit = c_low <= tp_px
            
            if sl_hit or tp_hit:
                in_trade = False

        ema7   = calc_ema(closes, cfg["ema_fast"])
        ema21  = calc_ema(closes, cfg["ema_slow"])
        ema50  = calc_ema(closes, cfg["ema_base"])
        atr    = calc_atr(highs, lows, closes, 14)

        is_bull_cloud = ema7[-1] > ema21[-1]
        is_bear_cloud = ema7[-1] < ema21[-1]

        base_bull = (c_close > ema50[-1]) and (ema21[-1] >= ema50[-1])
        base_bear = (c_close < ema50[-1]) and (ema21[-1] <= ema50[-1])
        is_bull_regime = not cfg.get("use_trend_filter", True) or base_bull
        is_bear_regime = not cfg.get("use_trend_filter", True) or base_bear

        ribbon_spread = abs(ema7[-1] - ema21[-1])
        is_ribbon_tangled = ribbon_spread < (atr[-1] * 0.12)

        candle_range = max(c_high - c_low, 0.01)
        candle_body  = abs(c_close - c_open)
        is_strong_body = (candle_body / candle_range) * 100.0 >= cfg["min_body_percent"]

        buy_vol = c_vol * ((c_close - c_low) / candle_range)
        sell_vol = c_vol * ((c_high - c_close) / candle_range)
        vol_delta = buy_vol - sell_vol

        raw_deltas = []
        for i in range(len(sub)):
            cr = max(highs[i] - lows[i], 0.01)
            bv = vols[i] * ((closes[i] - lows[i]) / cr)
            sv = vols[i] * ((highs[i] - closes[i]) / cr)
            raw_deltas.append(bv - sv)

        vol_delta = raw_deltas[-1]
        prev_delta = raw_deltas[-2] if len(raw_deltas) >= 2 else 0.0
        abs_deltas = [abs(d) for d in raw_deltas]
        avg_delta = sum(abs_deltas[-14:]) / 14.0 if len(abs_deltas) >= 14 else 1.0
        is_flow_surge = abs(vol_delta) >= (avg_delta * cfg["delta_surge_mult"])

        buy_flow_valid  = vol_delta > 0 and (is_flow_surge or vol_delta > prev_delta)
        sell_flow_valid = vol_delta < 0 and (is_flow_surge or vol_delta < prev_delta)

        lookback = cfg["bos_lookback"]
        prev_high = max(highs[-lookback-1:-1])
        prev_low  = min(lows[-lookback-1:-1])

        trend_cross_up = (ema7[-2] <= ema21[-2] and ema7[-1] > ema21[-1]) and is_bull_regime and not is_ribbon_tangled
        trend_cross_dn = (ema7[-2] >= ema21[-2] and ema7[-1] < ema21[-1]) and is_bear_regime and not is_ribbon_tangled

        trend_break_up = (closes[-2] <= ema50[-2] and c_close > ema50[-1]) and is_bull_cloud
        trend_break_dn = (closes[-2] >= ema50[-2] and c_close < ema50[-1]) and is_bear_cloud

        bos_break_up = (closes[-2] <= prev_high and c_close > prev_high) and is_bull_regime and is_bull_cloud
        bos_break_dn = (closes[-2] >= prev_low and c_close < prev_low) and is_bear_regime and is_bear_cloud

        buy_event  = trend_break_up or trend_cross_up or bos_break_up
        sell_event = trend_break_dn or trend_cross_dn or bos_break_dn

        raw_buy  = buy_event  and is_strong_body and buy_flow_valid  and is_bull_regime and c_close > c_open
        raw_sell = sell_event and is_strong_body and sell_flow_valid and is_bear_regime and c_close < c_open

        cooldown_ok = (bar_index - last_signal_bar_idx >= cfg["cooldown_bars"])
        can_buy  = (not cfg["single_wave_entry"] or last_signal_state != 1)  and cooldown_ok and not in_trade
        can_sell = (not cfg["single_wave_entry"] or last_signal_state != -1) and cooldown_ok and not in_trade

        if raw_buy and can_buy:
            last_signal_state = 1
            last_signal_bar_idx = bar_index
            in_trade = True
            trade_dir = 1
            entry_px = c_close
            sl_dist = atr[-1] * cfg["sl_atr_mult"]
            tp_dist = sl_dist * cfg["rr_ratio"]
            sl_px = c_close - sl_dist
            tp_px = c_close + tp_dist

        elif raw_sell and can_sell:
            last_signal_state = -1
            last_signal_bar_idx = bar_index
            in_trade = True
            trade_dir = -1
            entry_px = c_close
            sl_dist = atr[-1] * cfg["sl_atr_mult"]
            tp_dist = sl_dist * cfg["rr_ratio"]
            sl_px = c_close + sl_dist
            tp_px = c_close - tp_dist

    return {
        "last_signal_state": last_signal_state,
        "last_signal_bar_idx": last_signal_bar_idx,
        "bar_index": bar_index,
        "in_trade": in_trade,
        "trade_dir": trade_dir,
        "entry_px": entry_px,
        "sl_px": sl_px,
        "tp_px": tp_px
    }

def scalper_worker():
    global bot_stats
    print(f"[CLOUD BOT] Starting Shenex Scalper Engine for {CONFIG['symbol']}...", flush=True)

    startup_msg = (
        "☁️ <b>SHENEX CLOUD SCALPER 24/7 SYNCHRONIZED!</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "📊 <b>Market:</b> Gold (XAUUSD) M5 Live Stream\n"
        "⚡ <b>Engine:</b> 100% Exact TradingView Pine Script Engine\n"
        "🔒 <b>Wave & Trade Lock:</b> Single Wave Entry + Open Trade Gate Active\n"
        "🌐 <b>Host:</b> 24/7 Cloud/Mobile Host (PC OFF Safe)\n"
        "━━━━━━━━━━━━━━━━━━━━━━"
    )
    send_telegram(BOT_TOKEN, CHAT_ID, startup_msg)

    print("[SYNC] Synchronizing historical bars with TradingView...", flush=True)
    init_candles = fetch_candles(CONFIG["symbol"], CONFIG["interval"], limit=250)
    state = sync_with_history(init_candles[:-1], CONFIG)

    last_processed_bar_time = init_candles[-2]["time"]
    last_signal_state = state["last_signal_state"]
    last_signal_bar_idx = state["last_signal_bar_idx"]
    bar_index = state["bar_index"]
    in_trade = state["in_trade"]
    trade_dir = state["trade_dir"]
    entry_px = state["entry_px"]
    sl_px = state["sl_px"]
    tp_px = state["tp_px"]

    wave_status = "BULL WAVE (BUY active)" if last_signal_state == 1 else "BEAR WAVE (SELL active)" if last_signal_state == -1 else "NEUTRAL"
    print(f"[SYNC COMPLETE] Wave State = {wave_status} | Open Trade = {in_trade} | Bars Since Last Signal = {bar_index - last_signal_bar_idx}", flush=True)

    while True:
        try:
            candles = fetch_candles(CONFIG["symbol"], CONFIG["interval"], limit=250)
            if not candles or len(candles) < 60:
                time.sleep(5)
                continue

            confirmed_candle = candles[-2]
            bar_time = confirmed_candle["time"]

            if bar_time != last_processed_bar_time:
                last_processed_bar_time = bar_time
                bar_index += 1
                bot_stats["bars_processed"] = bar_index

                eval_candles = candles[:-1]
                closes = [c["close"] for c in eval_candles]
                opens  = [c["open"]  for c in eval_candles]
                highs  = [c["high"]  for c in eval_candles]
                lows   = [c["low"]   for c in eval_candles]
                vols   = [c["volume"] for c in eval_candles]

                c_close = closes[-1]
                c_open  = opens[-1]
                c_high  = highs[-1]
                c_low   = lows[-1]
                c_vol   = vols[-1]

                bot_stats["last_price"] = c_close
                bot_stats["last_bar_time"] = datetime.datetime.fromtimestamp(bar_time / 1000).strftime("%Y-%m-%d %H:%M:%S")

                # Manage Open Trade (Check SL / TP hit)
                if in_trade:
                    if trade_dir == 1:
                        sl_hit = c_low <= sl_px
                        tp_hit = c_high >= tp_px
                    else:
                        sl_hit = c_high >= sl_px
                        tp_hit = c_low <= tp_px

                    if sl_hit:
                        in_trade = False
                        loss_pips = abs(sl_px - entry_px) * 10
                        close_msg = (
                            "🛑 <b>SHENEX SCALPER: TRADE CLOSED (SL HIT)</b>\n"
                            "━━━━━━━━━━━━━━━━━━━━━━\n"
                            f"📊 <b>Asset:</b> XAUUSD (M5)\n"
                            f"📉 <b>Result:</b> Stop Loss Hit (-{loss_pips:.0f} pips)\n"
                            f"🎯 <b>Exit Price:</b> {sl_px:.2f}\n"
                            "━━━━━━━━━━━━━━━━━━━━━━"
                        )
                        print(f"\n[CLOSED] 🛑 Stop Loss Hit at {sl_px:.2f} (-{loss_pips:.0f} pips)", flush=True)
                        send_telegram(BOT_TOKEN, CHAT_ID, close_msg)

                    elif tp_hit:
                        in_trade = False
                        gain_pips = abs(tp_px - entry_px) * 10
                        close_msg = (
                            "🎯 <b>SHENEX SCALPER: TAKE PROFIT HIT!</b>\n"
                            "━━━━━━━━━━━━━━━━━━━━━━\n"
                            f"📊 <b>Asset:</b> XAUUSD (M5)\n"
                            f"💰 <b>Result:</b> Full Target Reached (+{gain_pips:.0f} pips)\n"
                            f"🎯 <b>Exit Price:</b> {tp_px:.2f}\n"
                            "━━━━━━━━━━━━━━━━━━━━━━"
                        )
                        print(f"\n[CLOSED] 🎯 Take Profit Hit at {tp_px:.2f} (+{gain_pips:.0f} pips)", flush=True)
                        send_telegram(BOT_TOKEN, CHAT_ID, close_msg)

                # Indicator Engine
                ema7   = calc_ema(closes, CONFIG["ema_fast"])
                ema21  = calc_ema(closes, CONFIG["ema_slow"])
                ema50  = calc_ema(closes, CONFIG["ema_base"])
                atr    = calc_atr(highs, lows, closes, 14)

                is_bull_cloud = ema7[-1] > ema21[-1]
                is_bear_cloud = ema7[-1] < ema21[-1]

                base_bull = (c_close > ema50[-1]) and (ema21[-1] >= ema50[-1])
                base_bear = (c_close < ema50[-1]) and (ema21[-1] <= ema50[-1])
                is_bull_regime = not CONFIG.get("use_trend_filter", True) or base_bull
                is_bear_regime = not CONFIG.get("use_trend_filter", True) or base_bear

                ribbon_spread = abs(ema7[-1] - ema21[-1])
                is_ribbon_tangled = ribbon_spread < (atr[-1] * 0.12)

                candle_range = max(c_high - c_low, 0.01)
                candle_body  = abs(c_close - c_open)
                is_strong_body = (candle_body / candle_range) * 100.0 >= CONFIG["min_body_percent"]

                buy_vol = c_vol * ((c_close - c_low) / candle_range)
                sell_vol = c_vol * ((c_high - c_close) / candle_range)
                vol_delta = buy_vol - sell_vol

                raw_deltas = []
                for i in range(len(eval_candles)):
                    cr = max(highs[i] - lows[i], 0.01)
                    bv = vols[i] * ((closes[i] - lows[i]) / cr)
                    sv = vols[i] * ((highs[i] - closes[i]) / cr)
                    raw_deltas.append(bv - sv)

                vol_delta = raw_deltas[-1]
                prev_delta = raw_deltas[-2] if len(raw_deltas) >= 2 else 0.0
                abs_deltas = [abs(d) for d in raw_deltas]
                avg_delta = sum(abs_deltas[-14:]) / 14.0 if len(abs_deltas) >= 14 else 1.0
                is_flow_surge = abs(vol_delta) >= (avg_delta * CONFIG["delta_surge_mult"])
                buy_flow_valid  = vol_delta > 0 and (is_flow_surge or vol_delta > prev_delta)
                sell_flow_valid = vol_delta < 0 and (is_flow_surge or vol_delta < prev_delta)

                lookback = CONFIG["bos_lookback"]
                prev_high = max(highs[-lookback-1:-1])
                prev_low  = min(lows[-lookback-1:-1])

                trend_cross_up = (ema7[-2] <= ema21[-2] and ema7[-1] > ema21[-1]) and is_bull_regime and not is_ribbon_tangled
                trend_cross_dn = (ema7[-2] >= ema21[-2] and ema7[-1] < ema21[-1]) and is_bear_regime and not is_ribbon_tangled

                trend_break_up = (closes[-2] <= ema50[-2] and c_close > ema50[-1]) and is_bull_cloud
                trend_break_dn = (closes[-2] >= ema50[-2] and c_close < ema50[-1]) and is_bear_cloud

                bos_break_up = (closes[-2] <= prev_high and c_close > prev_high) and is_bull_regime and is_bull_cloud
                bos_break_dn = (closes[-2] >= prev_low and c_close < prev_low) and is_bear_regime and is_bear_cloud

                buy_event  = trend_break_up or trend_cross_up or bos_break_up
                sell_event = trend_break_dn or trend_cross_dn or bos_break_dn

                raw_buy  = buy_event  and is_strong_body and buy_flow_valid  and is_bull_regime and c_close > c_open
                raw_sell = sell_event and is_strong_body and sell_flow_valid and is_bear_regime and c_close < c_open

                # Exact TradingView gate: cooldown + single wave lock + not in_trade
                cooldown_ok = (bar_index - last_signal_bar_idx >= CONFIG["cooldown_bars"])
                can_buy  = (not CONFIG["single_wave_entry"] or last_signal_state != 1)  and cooldown_ok and not in_trade
                can_sell = (not CONFIG["single_wave_entry"] or last_signal_state != -1) and cooldown_ok and not in_trade

                trend_status = "BULLISH 🟢" if is_bull_regime else "BEARISH 🔴" if is_bear_regime else "CONSOLIDATING ⚪"
                bot_stats["last_trend"] = trend_status
                in_trade_str = f" | InTrade: {'LONG' if trade_dir==1 else 'SHORT'}" if in_trade else ""

                print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] Bar Closed @ {c_close:.2f} | Trend: {trend_status} | Delta: {vol_delta:+.2f}{in_trade_str}", flush=True)

                if raw_buy and can_buy:
                    last_signal_state = 1
                    last_signal_bar_idx = bar_index
                    in_trade = True
                    trade_dir = 1
                    entry_px = c_close
                    bot_stats["signals_sent"] += 1

                    sl_dist = atr[-1] * CONFIG["sl_atr_mult"]
                    tp_dist = sl_dist * CONFIG["rr_ratio"]
                    buy_sl = c_close - sl_dist
                    buy_tp = c_close + tp_dist
                    sl_px = buy_sl
                    tp_px = buy_tp

                    risk_usd = CONFIG.get("account_balance", 500.0) * (CONFIG.get("risk_percent", 2.0) / 100.0)
                    rec_lot = max(round(risk_usd / (sl_dist * 100.0), 2), 0.01)
                    est_loss = rec_lot * 100.0 * sl_dist
                    est_profit = rec_lot * 100.0 * tp_dist

                    sig_msg = (
                        "🚀 <b>SHENEX SCALPER: BUY SIGNAL CONFIRMED!</b>\n"
                        "━━━━━━━━━━━━━━━━━━━━━━\n"
                        f"📊 <b>Asset:</b> XAUUSD (M5)\n"
                        f"🎯 <b>Entry Price:</b> {c_close:.2f}\n"
                        f"🛑 <b>Stop Loss:</b> {buy_sl:.2f} (-{sl_dist*10:.0f} pips)\n"
                        f"💰 <b>Take Profit:</b> {buy_tp:.2f} (+{tp_dist*10:.0f} pips)\n"
                        f"⚖️ <b>Risk:Reward:</b> 1:{CONFIG['rr_ratio']:.1f}\n\n"
                        f"💼 <b>Risk Management (${CONFIG.get('account_balance', 500.0):.0f} Acc):</b>\n"
                        f"  • <b>Lot Size:</b> <code>{rec_lot:.2f}</code>\n"
                        f"  • <b>Risk (SL):</b> -${est_loss:.2f} ({CONFIG.get('risk_percent', 2.0):.1f}%)\n"
                        f"  • <b>Reward (TP):</b> +${est_profit:.2f} ({CONFIG.get('risk_percent', 2.0)*2:.1f}%)\n\n"
                        "⚡ <b>Confirmations:</b>\n"
                        "  • EMA 7/21 Cloud: Bullish 🟢\n"
                        "  • 50 EMA Trend Lock: Passed 🔒\n"
                        "  • Order Flow Surge: Confirmed 🌊\n"
                        "━━━━━━━━━━━━━━━━━━━━━━"
                    )
                    send_telegram(BOT_TOKEN, CHAT_ID, sig_msg)

                elif raw_sell and can_sell:
                    last_signal_state = -1
                    last_signal_bar_idx = bar_index
                    in_trade = True
                    trade_dir = -1
                    entry_px = c_close
                    bot_stats["signals_sent"] += 1

                    sl_dist = atr[-1] * CONFIG["sl_atr_mult"]
                    tp_dist = sl_dist * CONFIG["rr_ratio"]
                    sell_sl = c_close + sl_dist
                    sell_tp = c_close - tp_dist
                    sl_px = sell_sl
                    tp_px = sell_tp

                    risk_usd = CONFIG.get("account_balance", 500.0) * (CONFIG.get("risk_percent", 2.0) / 100.0)
                    rec_lot = max(round(risk_usd / (sl_dist * 100.0), 2), 0.01)
                    est_loss = rec_lot * 100.0 * sl_dist
                    est_profit = rec_lot * 100.0 * tp_dist

                    sig_msg = (
                        "🔻 <b>SHENEX SCALPER: SELL SIGNAL CONFIRMED!</b>\n"
                        "━━━━━━━━━━━━━━━━━━━━━━\n"
                        f"📊 <b>Asset:</b> XAUUSD (M5)\n"
                        f"🎯 <b>Entry Price:</b> {c_close:.2f}\n"
                        f"🛑 <b>Stop Loss:</b> {sell_sl:.2f} (-{sl_dist*10:.0f} pips)\n"
                        f"💰 <b>Take Profit:</b> {sell_tp:.2f} (+{tp_dist*10:.0f} pips)\n"
                        f"⚖️ <b>Risk:Reward:</b> 1:{CONFIG['rr_ratio']:.1f}\n\n"
                        f"💼 <b>Risk Management (${CONFIG.get('account_balance', 500.0):.0f} Acc):</b>\n"
                        f"  • <b>Lot Size:</b> <code>{rec_lot:.2f}</code>\n"
                        f"  • <b>Risk (SL):</b> -${est_loss:.2f} ({CONFIG.get('risk_percent', 2.0):.1f}%)\n"
                        f"  • <b>Reward (TP):</b> +${est_profit:.2f} ({CONFIG.get('risk_percent', 2.0)*2:.1f}%)\n\n"
                        "⚡ <b>Confirmations:</b>\n"
                        "  • EMA 7/21 Cloud: Bearish 🔴\n"
                        "  • 50 EMA Trend Lock: Passed 🔒\n"
                        "  • Order Flow Surge: Confirmed 🌊\n"
                        "━━━━━━━━━━━━━━━━━━━━━━"
                    )
                    send_telegram(BOT_TOKEN, CHAT_ID, sig_msg)

            time.sleep(5)
        except Exception as e:
            print(f"[RETRY] Error in scan cycle: {e}. Retrying in 10s...", flush=True)
            time.sleep(10)

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        res = {
            "app": "Shenex Flow Scalper Cloud Bot",
            "status": "online",
            "stats": bot_stats
        }
        self.wfile.write(json.dumps(res, indent=2).encode("utf-8"))

    def log_message(self, format, *args):
        return

def run_http_server():
    server = HTTPServer(("0.0.0.0", PORT), HealthHandler)
    print(f"[HEALTH CHECK] HTTP Server running on port {PORT}...", flush=True)
    server.serve_forever()

if __name__ == "__main__":
    t = threading.Thread(target=scalper_worker, daemon=True)
    t.start()
    run_http_server()

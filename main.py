"""
====================================================================================================
                        SHENEX FLOW SCALPER PRO - 24/7 CLOUD BOT
               High-Conviction EMA 7/21 • Break of Structure • Order Flow Surge
               Strict 50/200 EMA Macro Trend Lock • 100% Free 24/7 Cloud Service
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
PORT = int(os.environ.get("PORT", 8080))

CONFIG = {
    "symbol": "PAXGUSDT",  # Gold (XAUUSD Pegged)
    "interval": "5m",
    "ema_fast": 7,
    "ema_slow": 21,
    "ema_base": 50,
    "ema_macro": 200,
    "bos_lookback": 8,
    "min_body_percent": 45.0,
    "delta_surge_mult": 1.1,
    "sl_atr_mult": 1.5,
    "rr_ratio": 2.0,
    "cooldown_bars": 8,
    "single_wave_entry": True
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

def fetch_candles(symbol="PAXGUSDT", interval="5m", limit=120):
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

def scalper_worker():
    global bot_stats
    print(f"[CLOUD BOT] Starting Shenex Scalper Engine for {CONFIG['symbol']}...", flush=True)

    # Startup Notification
    startup_msg = (
        "☁️ <b>SHENEX CLOUD SCALPER 24/7 ACTIVATED!</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "📊 <b>Market:</b> Gold (XAUUSD) M5 Live Stream\n"
        "⚡ <b>Engine:</b> Institutional EMA 7/21 & Structure Engine\n"
        "🔒 <b>Trend Lock:</b> 50 & 200 EMA Active\n"
        "🌐 <b>Host:</b> 24/7 Cloud Server (Runs even when PC is OFF)\n"
        "━━━━━━━━━━━━━━━━━━━━━━"
    )
    send_telegram(BOT_TOKEN, CHAT_ID, startup_msg)

    last_processed_bar_time = 0
    last_signal_state = 0
    last_signal_bar_idx = -100
    bar_index = 0

    while True:
        try:
            candles = fetch_candles(CONFIG["symbol"], CONFIG["interval"], limit=220)
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

                ema7   = calc_ema(closes, CONFIG["ema_fast"])
                ema21  = calc_ema(closes, CONFIG["ema_slow"])
                ema50  = calc_ema(closes, CONFIG["ema_base"])
                ema200 = calc_ema(closes, CONFIG["ema_macro"])
                atr    = calc_atr(highs, lows, closes, 14)

                is_bull_cloud = ema7[-1] > ema21[-1]
                is_bear_cloud = ema7[-1] < ema21[-1]

                base_bull  = c_close > ema50[-1] and ema21[-1] >= ema50[-1]
                base_bear  = c_close < ema50[-1] and ema21[-1] <= ema50[-1]
                macro_bull = c_close > ema200[-1] and ema50[-1] >= ema200[-1]
                macro_bear = c_close < ema200[-1] and ema50[-1] <= ema200[-1]

                is_bull_regime = base_bull and macro_bull
                is_bear_regime = base_bear and macro_bear

                ribbon_spread = abs(ema7[-1] - ema21[-1])
                is_ribbon_tangled = ribbon_spread < (atr[-1] * 0.12)

                candle_range = max(c_high - c_low, 0.01)
                candle_body  = abs(c_close - c_open)
                is_strong_body = (candle_body / candle_range) * 100.0 >= CONFIG["min_body_percent"]

                buy_vol = c_vol * ((c_close - c_low) / candle_range)
                sell_vol = c_vol * ((c_high - c_close) / candle_range)
                vol_delta = buy_vol - sell_vol

                deltas = []
                for i in range(len(eval_candles)):
                    cr = max(highs[i] - lows[i], 0.01)
                    bv = vols[i] * ((closes[i] - lows[i]) / cr)
                    sv = vols[i] * ((highs[i] - closes[i]) / cr)
                    deltas.append(abs(bv - sv))

                avg_delta = sum(deltas[-14:]) / 14.0 if len(deltas) >= 14 else 1.0
                is_flow_surge = abs(vol_delta) >= (avg_delta * CONFIG["delta_surge_mult"])

                prev_delta = deltas[-2] if len(deltas) >= 2 else 0.0
                buy_flow_valid  = vol_delta > 0 and (is_flow_surge or vol_delta > prev_delta)
                sell_flow_valid = vol_delta < 0 and (is_flow_surge or vol_delta < prev_delta)

                lookback = CONFIG["bos_lookback"]
                prev_high = max(highs[-lookback-1:-1])
                prev_low  = min(lows[-lookback-1:-1])

                bos_break_up = (closes[-2] <= prev_high and c_close > prev_high) and is_bull_regime and is_bull_cloud
                bos_break_dn = (closes[-2] >= prev_low and c_close < prev_low) and is_bear_regime and is_bear_cloud

                trend_cross_up = (ema7[-2] <= ema21[-2] and ema7[-1] > ema21[-1]) and is_bull_regime and not is_ribbon_tangled
                trend_cross_dn = (ema7[-2] >= ema21[-2] and ema7[-1] < ema21[-1]) and is_bear_regime and not is_ribbon_tangled

                trend_break_up = (closes[-2] <= ema50[-2] and c_close > ema50[-1]) and is_bull_cloud
                trend_break_dn = (closes[-2] >= ema50[-2] and c_close < ema50[-1]) and is_bear_cloud

                buy_event  = trend_break_up or trend_cross_up or bos_break_up
                sell_event = trend_break_dn or trend_cross_dn or bos_break_dn

                raw_buy  = buy_event  and is_strong_body and buy_flow_valid  and is_bull_regime and c_close > c_open
                raw_sell = sell_event and is_strong_body and sell_flow_valid and is_bear_regime and c_close < c_open

                cooldown_ok = (bar_index - last_signal_bar_idx >= CONFIG["cooldown_bars"])
                can_buy  = (not CONFIG["single_wave_entry"] or last_signal_state != 1)  and cooldown_ok
                can_sell = (not CONFIG["single_wave_entry"] or last_signal_state != -1) and cooldown_ok

                trend_status = "BULLISH 🟢" if is_bull_regime else "BEARISH 🔴" if is_bear_regime else "CONSOLIDATING ⚪"
                bot_stats["last_trend"] = trend_status

                print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] Bar Closed @ {c_close:.2f} | Trend: {trend_status} | Delta: {vol_delta:+.2f}", flush=True)

                if raw_buy and can_buy:
                    last_signal_state = 1
                    last_signal_bar_idx = bar_index
                    bot_stats["signals_sent"] += 1

                    sl_dist = atr[-1] * CONFIG["sl_atr_mult"]
                    tp_dist = sl_dist * CONFIG["rr_ratio"]
                    buy_sl = c_close - sl_dist
                    buy_tp = c_close + tp_dist

                    sig_msg = (
                        "🚀 <b>SHENEX SCALPER: BUY SIGNAL CONFIRMED!</b>\n"
                        "━━━━━━━━━━━━━━━━━━━━━━\n"
                        f"📊 <b>Asset:</b> XAUUSD (M5)\n"
                        f"🎯 <b>Entry Price:</b> {c_close:.2f}\n"
                        f"🛑 <b>Stop Loss:</b> {buy_sl:.2f} (-{sl_dist*10:.0f} pips)\n"
                        f"💰 <b>Take Profit:</b> {buy_tp:.2f} (+{tp_dist*10:.0f} pips)\n"
                        f"⚖️ <b>Risk:Reward:</b> 1:{CONFIG['rr_ratio']:.1f}\n\n"
                        "⚡ <b>Confirmations:</b>\n"
                        "  • EMA 7/21 Cloud: Bullish 🟢\n"
                        "  • 50 & 200 EMA Trend Lock: Passed 🔒\n"
                        "  • Order Flow Surge: Confirmed 🌊\n"
                        "━━━━━━━━━━━━━━━━━━━━━━"
                    )
                    send_telegram(BOT_TOKEN, CHAT_ID, sig_msg)

                elif raw_sell and can_sell:
                    last_signal_state = -1
                    last_signal_bar_idx = bar_index
                    bot_stats["signals_sent"] += 1

                    sl_dist = atr[-1] * CONFIG["sl_atr_mult"]
                    tp_dist = sl_dist * CONFIG["rr_ratio"]
                    sell_sl = c_close + sl_dist
                    sell_tp = c_close - tp_dist

                    sig_msg = (
                        "🔻 <b>SHENEX SCALPER: SELL SIGNAL CONFIRMED!</b>\n"
                        "━━━━━━━━━━━━━━━━━━━━━━\n"
                        f"📊 <b>Asset:</b> XAUUSD (M5)\n"
                        f"🎯 <b>Entry Price:</b> {c_close:.2f}\n"
                        f"🛑 <b>Stop Loss:</b> {sell_sl:.2f} (-{sl_dist*10:.0f} pips)\n"
                        f"💰 <b>Take Profit:</b> {sell_tp:.2f} (+{tp_dist*10:.0f} pips)\n"
                        f"⚖️ <b>Risk:Reward:</b> 1:{CONFIG['rr_ratio']:.1f}\n\n"
                        "⚡ <b>Confirmations:</b>\n"
                        "  • EMA 7/21 Cloud: Bearish 🔴\n"
                        "  • 50 & 200 EMA Trend Lock: Passed 🔒\n"
                        "  • Order Flow Surge: Confirmed 🌊\n"
                        "━━━━━━━━━━━━━━━━━━━━━━"
                    )
                    send_telegram(BOT_TOKEN, CHAT_ID, sig_msg)

            time.sleep(5)
        except Exception as e:
            print(f"[RETRY] Error in scan cycle: {e}. Retrying in 10s...", flush=True)
            time.sleep(10)

# Lightweight HTTP Health Check Server (For Render / Koyeb 24/7 Keep-Alive)
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
        return  # Suppress HTTP log spam

def run_http_server():
    server = HTTPServer(("0.0.0.0", PORT), HealthHandler)
    print(f"[HEALTH CHECK] HTTP Server running on port {PORT}...", flush=True)
    server.serve_forever()

if __name__ == "__main__":
    # Start Scalper in daemon thread
    t = threading.Thread(target=scalper_worker, daemon=True)
    t.start()

    # Run HTTP Server on main thread (keeps container/service alive)
    run_http_server()

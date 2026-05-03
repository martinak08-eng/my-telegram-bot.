import os

import time

import requests

import threading

import hashlib

from flask import Flask

TOKEN = os.getenv("TELEGRAM_TOKEN")

CHAT_ID = os.getenv("CHAT_ID")

BINANCE = "https://api.binance.com"

app = Flask(__name__)

@app.route('/')

def home():

    return "✅ BOT WORKING"

# ================= STATE =================

SIGNALS_SENT = {}

SIGNAL_TTL = 10800  # 3 години

STATS = {"signals": 0, "last": "None"}

# ================= TELEGRAM =================

def send(text):

    try:

        requests.post(

            f"https://api.telegram.org/bot{TOKEN}/sendMessage",

            json={"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown"},

            timeout=10

        )

    except:

        pass

# ================= АНТИ-ДУБЛІ =================

def is_duplicate(symbol, side):

    key = hashlib.md5(f"{symbol}_{side}".encode()).hexdigest()

    now = time.time()

    if key in SIGNALS_SENT:

        if now - SIGNALS_SENT[key] < SIGNAL_TTL:

            return True

    SIGNALS_SENT[key] = now

    return False

# ================= АНАЛІЗ =================

class Analyzer:

    def get_klines(self, symbol):

        try:

            r = requests.get(f"{BINANCE}/api/v3/klines",

                             params={"symbol": symbol, "interval": "5m", "limit": 50},

                             timeout=10)

            return r.json()

        except:

            return None

    def strong_signal(self, symbol):

        data = self.get_klines(symbol)

        if not data: return None

        closes = [float(x[4]) for x in data]

        highs = [float(x[2]) for x in data]

        lows = [float(x[3]) for x in data]

        vol = [float(x[5]) for x in data]

        price = closes[-1]

        avg_vol = sum(vol[-20:]) / 20

        vol_spike = vol[-1] > avg_vol * 2

        range_high = max(highs[-20:])

        range_low = min(lows[-20:])

        # LONG SMC

        if price < range_low * 1.002 and vol_spike:

            sl = min(lows[-10:])

            tp = price + (price - sl) * 3

            return self.build(symbol, "LONG", price, tp, sl, "SMC")

        # SHORT SMC

        if price > range_high * 0.998 and vol_spike:

            sl = max(highs[-10:])

            tp = price - (sl - price) * 3

            return self.build(symbol, "SHORT", price, tp, sl, "SMC")

        return None

    def fast_signal(self, symbol, change):

        price = float(change['lastPrice'])

        change_pct = float(change['priceChangePercent'])

        if abs(change_pct) < 5:

            return None

        side = "LONG" if change_pct > 0 else "SHORT"

        if is_duplicate(symbol, side):

            return None

        tp = price * (1.02 if side == "LONG" else 0.98)

        sl = price * (0.99 if side == "LONG" else 1.01)

        return (

            f"⚡️ *FAST SIGNAL*\n"

            f"{symbol}\n"

            f"{side}\n"

            f"Entry: {price:.4f}\n"

            f"TP: {tp:.4f}\n"

            f"SL: {sl:.4f}\n"

            f"Move: {round(change_pct,2)}%"

        )

    def build(self, symbol, side, entry, tp, sl, mode):

        if is_duplicate(symbol, side):

            return None

        STATS["signals"] += 1

        STATS["last"] = symbol

        return (

            f"🔥 *{mode} SIGNAL*\n"

            f"{symbol}\n"

            f"{side}\n\n"

            f"Entry: {entry:.4f}\n"

            f"TP: {tp:.4f}\n"

            f"SL: {sl:.4f}\n\n"

            f"RR 1:3 ✅"

        )

bot = Analyzer()

# ================= СКАНЕР =================

def scanner():

    send("🚀 БОТ ЗАПУЩЕНИЙ (NEW LOGIC)")

    while True:

        try:

            tickers = requests.get(f"{BINANCE}/api/v3/ticker/24hr").json()

            # ТОП 100 по обʼєму

            coins = sorted(

                [x for x in tickers if x['symbol'].endswith("USDT")],

                key=lambda x: float(x['quoteVolume']),

                reverse=True

            )[:100]

            for coin in coins:

                symbol = coin['symbol']

                # 1. STRONG сигнал

                sig = bot.strong_signal(symbol)

                if sig:

                    send(sig)

                    time.sleep(1)

                    continue

                # 2. FAST сигнал

                sig = bot.fast_signal(symbol, coin)

                if sig:

                    send(sig)

                    time.sleep(1)

        except Exception as e:

            print("ERROR:", e)

        time.sleep(300)

# ================= TELEGRAM =================

def telegram():

    last = 0

    while True:

        try:

            r = requests.get(

                f"https://api.telegram.org/bot{TOKEN}/getUpdates?offset={last+1}&timeout=30"

            ).json()

            for u in r.get("result", []):

                last = u["update_id"]

                text = u.get("message", {}).get("text", "")

                if text == "/status":

                    send(f"📊 Signals: {STATS['signals']}\nLast: {STATS['last']}")

                elif text == "/debug":

                    send("🧠 NEW LOGIC ACTIVE:\nSMC + FAST + AntiSpam")

                elif text == "/mode":

                    send("⚙️ Modes:\n1. SMC (strong)\n2. FAST (pump catch)")

                elif text == "/help":

                    send("/status\n/debug\n/mode")

        except:

            time.sleep(5)

# ================= START =================

if __name__ == "__main__":

    threading.Thread(target=lambda: app.run(host="0.0.0.0", port=int(os.getenv("PORT", 8080))), daemon=True).start()

    threading.Thread(target=scanner, daemon=True).start()

    telegram()

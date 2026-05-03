import os

import requests

import time

import hashlib

import threading

from flask import Flask

# ================= CONFIG =================

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

CHAT_ID = os.getenv("CHAT_ID")

if not TELEGRAM_TOKEN or not CHAT_ID:

    raise Exception("❌ Немає TELEGRAM_TOKEN або CHAT_ID")

# ================= WEB SERVER (Railway MUST HAVE) =================

app = Flask(__name__)

@app.route("/")

def home():

    return "✅ BOT WORKING V2.1"

def run_web():

    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))

# ================= STATE =================

SIGNAL_CACHE = {}

SIGNAL_TTL = 7200  # 2 години

LAST_SCAN = None

OPEN_TRADES = []

STATS = {"win": 0, "loss": 0}

# ================= TELEGRAM =================

def send(msg):

    try:

        requests.post(

            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",

            data={"chat_id": CHAT_ID, "text": msg},

            timeout=10

        )

    except:

        pass

# ================= АНТИ-ДУБЛІКАТ =================

def is_duplicate(symbol, side, entry):

    key = hashlib.md5(f"{symbol}_{side}_{round(entry,3)}".encode()).hexdigest()

    now = time.time()

    # очищення старих

    for k in list(SIGNAL_CACHE.keys()):

        if now - SIGNAL_CACHE[k] > SIGNAL_TTL:

            del SIGNAL_CACHE[k]

    if key in SIGNAL_CACHE:

        return True

    SIGNAL_CACHE[key] = now

    return False

# ================= BINANCE =================

def get_all_symbols():

    try:

        data = requests.get("https://api.binance.com/api/v3/ticker/24hr", timeout=10).json()

        coins = []

        for c in data:

            sym = c["symbol"]

            if not sym.endswith("USDT"):

                continue

            volume = float(c["quoteVolume"])

            change = abs(float(c["priceChangePercent"]))

            # ФІЛЬТР ЯКОСТІ (ВАЖЛИВО)

            if volume > 20_000_000 and change > 1:

                coins.append((sym, volume))

        coins.sort(key=lambda x: -x[1])

        return [c[0] for c in coins[:100]]  # ТОП 100

    except:

        return []

# ================= СТРАТЕГІЯ =================

def analyze(symbol):

    try:

        k = requests.get(

            "https://api.binance.com/api/v3/klines",

            params={"symbol": symbol, "interval": "5m", "limit": 50},

            timeout=10

        ).json()

        closes = [float(x[4]) for x in k]

        highs = [float(x[2]) for x in k]

        lows = [float(x[3]) for x in k]

        volume = [float(x[5]) for x in k]

        price = closes[-1]

        # ТРЕНД

        ma = sum(closes[-20:]) / 20

        trend = "LONG" if price > ma else "SHORT"

        # ІМПУЛЬС

        impulse = (closes[-1] - closes[-5]) / closes[-5] * 100

        # ОБʼЄМ

        avg_vol = sum(volume[:-1]) / len(volume[:-1])

        spike = volume[-1] > avg_vol * 2

        # ЛІКВІДНІСТЬ

        sweep_high = price >= max(highs[-20:])

        sweep_low = price <= min(lows[-20:])

        # ================= ЛОГІКА =================

        if trend == "LONG" and sweep_low and spike and impulse > 1.8:

            sl = min(lows[-20:])

            tp = price + (price - sl) * 3

            if is_duplicate(symbol, "LONG", price):

                return None

            return build_signal(symbol, "LONG", price, tp, sl, impulse)

        if trend == "SHORT" and sweep_high and spike and impulse < -1.8:

            sl = max(highs[-20:])

            tp = price - (sl - price) * 3

            if is_duplicate(symbol, "SHORT", price):

                return None

            return build_signal(symbol, "SHORT", price, tp, sl, impulse)

    except:

        return None

    return None

# ================= SIGNAL =================

def build_signal(symbol, side, entry, tp, sl, impulse):

    rr = abs((tp - entry) / (entry - sl))

    if rr < 2.5:

        return None

    text = f"""

🚀 SIGNAL V2.1

Coin: {symbol}

Side: {side}

Entry: {round(entry,4)}

TP: {round(tp,4)}

SL: {round(sl,4)}

RR: 1:{round(rr,2)}

Impulse: {round(impulse,2)}%

Reason:

- Liquidity sweep

- Volume spike

- Trend confirm

"""

    OPEN_TRADES.append({

        "symbol": symbol,

        "side": side,

        "tp": tp,

        "sl": sl

    })

    return text

# ================= MARKET LOOP =================

def market_loop():

    global LAST_SCAN

    send("✅ BOT V2.1 STARTED (FULL MARKET SCAN)")

    while True:

        try:

            symbols = get_all_symbols()

            for s in symbols:

                signal = analyze(s)

                if signal:

                    send(signal)

                    time.sleep(1)

            LAST_SCAN = time.strftime("%H:%M:%S")

        except Exception as e:

            send(f"⚠️ Error: {e}")

        time.sleep(300)  # 5 хв

# ================= COMMAND CHECK =================

def command_loop():

    last_update = 0

    while True:

        try:

            r = requests.get(

                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates",

                params={"offset": last_update + 1, "timeout": 30},

                timeout=35

            ).json()

            for u in r["result"]:

                last_update = u["update_id"]

                msg = u.get("message", {})

                text = msg.get("text", "")

                if text == "/check":

                    send("✅ BOT V2.1 ACTIVE (NEW CODE WORKING)")

                if text == "/status":

                    send(f"📊 Last scan: {LAST_SCAN}\nOpen trades: {len(OPEN_TRADES)}")

        except:

            pass

        time.sleep(2)

# ================= MAIN =================

if __name__ == "__main__":

    threading.Thread(target=run_web).start()

    threading.Thread(target=market_loop).start()

    threading.Thread(target=command_loop).start()

import os, requests, time, threading, hashlib

from flask import Flask, request

from threading import Thread

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")

CHAT_ID = os.environ.get("CHAT_ID")

app = Flask('')

# ================= STATE =================

OPEN_TRADES = []

LAST_SIGNAL_TIME = 0

GLOBAL_COOLDOWN = 10

SYMBOL_COOLDOWN = {}

SYMBOL_BLOCK_TIME = 3600

# ================= TELEGRAM =================

def send(msg):

    global LAST_SIGNAL_TIME

    now = time.time()

    if now - LAST_SIGNAL_TIME < GLOBAL_COOLDOWN:

        return

    LAST_SIGNAL_TIME = now

    try:

        requests.post(

            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",

            data={"chat_id": CHAT_ID, "text": msg},

            timeout=10

        )

    except:

        pass

# ================= COMMANDS =================

@app.route('/webhook', methods=['POST'])

def webhook():

    try:

        update = request.get_json()

        if "message" in update:

            text = update["message"]["text"].lower()

            if "статус" in text:

                send(f"🤖 BOT STATUS\nАктивні угоди: {len(OPEN_TRADES)}")

            elif "угоди" in text:

                if not OPEN_TRADES:

                    send("Немає відкритих угод")

                else:

                    msg = "📈 Угоди:\n"

                    for t in OPEN_TRADES:

                        msg += f"{t['symbol']} {t['side']}\n"

                    send(msg)

    except:

        pass

    return "ok"

@app.route('/')

def home():

    return "Bot running"

# ================= DATA =================

def get_symbols():

    data = requests.get("https://api.binance.com/api/v3/ticker/24hr").json()

    coins = []

    for c in data:

        try:

            if c["symbol"].endswith("USDT"):

                vol = float(c["quoteVolume"])

                if vol > 50000000:

                    coins.append((c["symbol"], vol))

        except:

            continue

    coins.sort(key=lambda x: -x[1])

    return [c[0] for c in coins[:50]]

def klines(symbol, tf="5m"):

    return requests.get(

        "https://api.binance.com/api/v3/klines",

        params={"symbol":symbol,"interval":tf,"limit":100}

    ).json()

# ================= ANALYSIS =================

def trend(closes):

    ma20 = sum(closes[-20:]) / 20

    ma50 = sum(closes[-50:]) / 50

    return "LONG" if ma20 > ma50 else "SHORT"

def confidence(vol_spike, imp, trend_match):

    score = 0

    if vol_spike: score += 40

    if abs(imp) > 3: score += 30

    if trend_match: score += 30

    return score

# ================= SIGNAL =================

def build(symbol, side, price, tp, sl, imp, conf, mode):

    now = time.time()

    if symbol in SYMBOL_COOLDOWN:

        if now - SYMBOL_COOLDOWN[symbol] < SYMBOL_BLOCK_TIME:

            return None

    SYMBOL_COOLDOWN[symbol] = now

    OPEN_TRADES.append({"symbol":symbol,"side":side})

    return f"""🔥 {mode}

{symbol} {side}

Entry: {round(price,4)}

TP: {round(tp,4)}

SL: {round(sl,4)}

Impulse: {round(imp,2)}%

Confidence: {conf}%"""

# ================= STRATEGIES =================

def smart_money(symbol):

    k = klines(symbol, "15m")

    if not k or len(k) < 50:

        return None

    closes = [float(x[4]) for x in k]

    vol = [float(x[5]) for x in k]

    t = trend(closes)

    imp = (closes[-1] - closes[-5]) / closes[-5] * 100

    avg_vol = sum(vol[-20:]) / 20

    vol_spike = vol[-1] > avg_vol * 2

    conf = confidence(vol_spike, imp, True)

    if vol_spike and abs(imp) > 2:

        price = closes[-1]

        if t == "LONG":

            sl = price * 0.99

            tp = price * 1.03

            return build(symbol,"LONG",price,tp,sl,imp,conf,"SMART")

        else:

            sl = price * 1.01

            tp = price * 0.97

            return build(symbol,"SHORT",price,tp,sl,imp,conf,"SMART")

def pump(symbol):

    k = klines(symbol,"5m")

    if not k: return None

    closes = [float(x[4]) for x in k]

    vol = [float(x[5]) for x in k]

    imp = (closes[-1] - closes[-3]) / closes[-3] * 100

    avg_vol = sum(vol[:-1]) / len(vol[:-1])

    if vol[-1] > avg_vol * 3 and abs(imp) > 3:

        price = closes[-1]

        side = "LONG" if imp > 0 else "SHORT"

        sl = price * (0.995 if side=="LONG" else 1.005)

        tp = price * (1.03 if side=="LONG" else 0.97)

        return build(symbol,side,price,tp,sl,imp,80,"PUMP")

# ================= MAIN =================

def run():

    send("🚀 BOT STARTED")

    while True:

        symbols = get_symbols()

        for s in symbols:

            try:

                sig = smart_money(s) or pump(s)

                if sig:

                    send(sig)

                    break

            except:

                continue

        time.sleep(300)

# ================= START =================

if __name__ == "__main__":

    Thread(target=lambda: app.run(host="0.0.0.0", port=8080)).start()

    run()



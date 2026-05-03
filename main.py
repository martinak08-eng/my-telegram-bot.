import os, requests, time, threading, hashlib

from flask import Flask, request

from threading import Thread

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")

CHAT_ID = os.environ.get("CHAT_ID")

app = Flask('')

# ================= VERSION =================

BOT_VERSION = "2.0 PRO"

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

            # 🔥 НОВА КОМАНДА

            if "/version" in text:

                send(f"""🤖 BOT VERSION: {BOT_VERSION}

✅ Новий фільтр монет активний

✅ Антиспам працює

✅ Smart Money + Pump режим

✅ Скан: весь Binance

Server: ONLINE

""")

            elif "статус" in text:

                send(f"🤖 STATUS\nУгоди: {len(OPEN_TRADES)}")

            elif "угоди" in text:

                if not OPEN_TRADES:

                    send("Немає угод")

                else:

                    msg = "📈 Угоди:\n"

                    for t in OPEN_TRADES:

                        msg += f"{t['symbol']} {t['side']}\n"

                    send(msg)

            elif "watchlist" in text:

                coins = get_symbols_full()

                msg = "🔥 ТОП РУХ:\n\n"

                for c in coins[:15]:

                    msg += f"{c[0]} | {round(c[1],2)}%\n"

                send(msg)

    except:

        pass

    return "ok"

@app.route('/')

def home():

    return f"Bot running | version {BOT_VERSION}"

# ================= DATA =================

def get_symbols():

    data = requests.get("https://api.binance.com/api/v3/ticker/24hr").json()

    return [c["symbol"] for c in data if c["symbol"].endswith("USDT")]

def get_symbols_full():

    data = requests.get("https://api.binance.com/api/v3/ticker/24hr").json()

    coins = []

    for c in data:

        try:

            if c["symbol"].endswith("USDT"):

                change = float(c["priceChangePercent"])

                vol = float(c["quoteVolume"])

                if vol > 30000000:

                    score = abs(change) + (vol / 10000000)

                    coins.append((c["symbol"], change, score))

        except:

            continue

    coins.sort(key=lambda x: -x[2])

    return coins[:50]

# ================= FILTER =================

def filter_best(symbols):

    best = []

    for s in symbols:

        try:

            data = requests.get(

                "https://api.binance.com/api/v3/ticker/24hr",

                params={"symbol": s}

            ).json()

            change = abs(float(data["priceChangePercent"]))

            vol = float(data["quoteVolume"])

            if vol > 50000000 and change > 2.5:

                best.append((s, change))

        except:

            continue

    best.sort(key=lambda x: -x[1])

    return [b[0] for b in best[:20]]

# ================= ANALYSIS =================

def klines(symbol, tf="5m"):

    return requests.get(

        "https://api.binance.com/api/v3/klines",

        params={"symbol":symbol,"interval":tf,"limit":100}

    ).json()

def trend(closes):

    return "LONG" if sum(closes[-20:])/20 > sum(closes[-50:])/50 else "SHORT"

def impulse(closes):

    return (closes[-1] - closes[-5]) / closes[-5] * 100

def volume_spike(vol):

    avg = sum(vol[-20:]) / 20

    return vol[-1] > avg * 2

# ================= SIGNAL =================

def build(symbol, side, price, tp, sl, imp):

    now = time.time()

    if symbol in SYMBOL_COOLDOWN:

        if now - SYMBOL_COOLDOWN[symbol] < SYMBOL_BLOCK_TIME:

            return None

    SYMBOL_COOLDOWN[symbol] = now

    rr = abs((tp-price)/(price-sl))

    if rr < 3:

        return None

    OPEN_TRADES.append({"symbol":symbol,"side":side})

    return f"""🔥 SIGNAL

{symbol} {side}

Entry: {round(price,4)}

TP: {round(tp,4)}

SL: {round(sl,4)}

Impulse: {round(imp,2)}%

"""

# ================= STRATEGIES =================

def smart_money(symbol):

    k = klines(symbol,"15m")

    if not k or len(k)<50:

        return None

    closes=[float(x[4]) for x in k]

    vol=[float(x[5]) for x in k]

    if not volume_spike(vol):

        return None

    t=trend(closes)

    imp=impulse(closes)

    price=closes[-1]

    if t=="LONG":

        return build(symbol,"LONG",price,price*1.03,price*0.99,imp)

    else:

        return build(symbol,"SHORT",price,price*0.97,price*1.01,imp)

def pump(symbol):

    k=klines(symbol,"5m")

    if not k:

        return None

    closes=[float(x[4]) for x in k]

    vol=[float(x[5]) for x in k]

    imp=impulse(closes)

    avg=sum(vol[:-1])/len(vol[:-1])

    if vol[-1]>avg*3 and abs(imp)>3:

        price=closes[-1]

        side="LONG" if imp>0 else "SHORT"

        return build(symbol,side,price,price*1.03,price*0.995,imp)

# ================= MAIN =================

def run():

    send(f"🚀 BOT STARTED | {BOT_VERSION}")

    while True:

        all_symbols = get_symbols()

        symbols = filter_best(all_symbols)

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

import os
import requests, time, threading, hashlib, json as _json
from datetime import datetime
from flask import Flask
from threading import Thread

# ================= CONFIG =================

# 1. ВСТАВТЕ ВАШ ТОКЕН ТА ID ТУТ:
TELEGRAM_TOKEN = "8694956837:AAEo0thSc3rdboV40YQHW6L7_JcgyjJbH2E"
CHAT_ID = "5903555117"

# 2. НАЛАШТУВАННЯ ПРОКСІ (Обов'язково для PythonAnywhere)
PROXY_URL = "http://proxy.server:3128"
proxies = {
    "http": PROXY_URL,
    "https": PROXY_URL,
}

# ================= KEEP ALIVE =================
app = Flask('')
@app.route('/')
def home():
    return "Bot is running"

def run_web():
    # На PythonAnywhere порт ігнорується у Flask, але для коду залишимо
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    Thread(target=run_web, daemon=True).start()

# ================= ENDPOINTS =================
# Змінено на основні API, щоб проксі легше пропускав запити
BNC_KLINES = "https://api.binance.com/api/v3/klines"
BNC_TICKER_24H = "https://api.binance.com/api/v3/ticker/24hr"
OKX_FUNDING = "https://www.okx.com/api/v5/public/funding-rate"

# ================= SETTINGS =================
MIN_VOLUME = 50000000
MIN_IMPULSE = 3
MIN_RR = 3

# ================= STATE =================
COOLDOWN = {}
COOLDOWN_TIME = 3600
OPEN_TRADES = []
STATS = {"win": 0, "loss": 0}
SIGNAL_CACHE = {}
SIGNAL_TTL = 7200
LAST_SIGNAL_PER_SYMBOL = {}
SIGNAL_REPEAT_BLOCK = 7200

# ================= ANTI-DUPLICATE =================
def is_duplicate(symbol, side, entry, tp, sl):
    key = f"{symbol}_{side}_{round(entry,4)}_{round(tp,4)}_{round(sl,4)}"
    key = hashlib.md5(key.encode()).hexdigest()
    now = time.time()
    for k in list(SIGNAL_CACHE.keys()):
        if now - SIGNAL_CACHE[k] > SIGNAL_TTL:
            del SIGNAL_CACHE[k]
    if key in SIGNAL_CACHE:
        return True
    SIGNAL_CACHE[key] = now
    return False

def is_duplicate_advanced(symbol, side):
    now = time.time()
    if symbol in LAST_SIGNAL_PER_SYMBOL:
        t, s = LAST_SIGNAL_PER_SYMBOL[symbol]
        if now - t < SIGNAL_REPEAT_BLOCK and s == side:
            return True
    LAST_SIGNAL_PER_SYMBOL[symbol] = (now, side)
    return False

# ================= TELEGRAM =================
def send(msg):
    try:
        # Додано proxies=proxies
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            data={"chat_id": CHAT_ID, "text": msg},
            proxies=proxies,
            timeout=10
        )
    except Exception as e:
        print(f"Помилка Telegram: {e}")

# ================= DATA =================
def safe_get(url, params=None):
    try:
        # Додано proxies=proxies
        r = requests.get(url, params=params, proxies=proxies, timeout=15)
        return r.json() if r.status_code == 200 else None
    except Exception as e:
        print(f"Помилка API ({url}): {e}")
        return None

def get_symbols():
    data = safe_get(BNC_TICKER_24H)
    coins = []
    if not isinstance(data, list):
        return []
    for c in data:
        try:
            if not c["symbol"].endswith("USDT"): continue
            vol = float(c["quoteVolume"])
            change = abs(float(c["priceChangePercent"]))
            if vol > MIN_VOLUME and change > 2:
                coins.append((c["symbol"], vol))
        except: continue
    coins.sort(key=lambda x: -x[1])
    return [c[0] for c in coins[:30]]

def get_klines(symbol, tf="5m"):
    return safe_get(BNC_KLINES, {"symbol": symbol, "interval": tf, "limit": 120})

# ================= LOGIC & STRATEGIES =================
def is_strong_trend(closes):
    if len(closes) < 20: return False
    ma_fast = sum(closes[-10:]) / 10
    ma_slow = sum(closes[-20:]) / 20
    return abs(ma_fast - ma_slow) / ma_slow > 0.005

def build_signal(symbol, side, entry, tp, sl, impulse):
    try:
        rr = abs((tp - entry) / (entry - sl))
    except: return None
    if rr < MIN_RR or abs(impulse) < MIN_IMPULSE: return None
    if is_duplicate(symbol, side, entry, tp, sl): return None
    if is_duplicate_advanced(symbol, side): return None
    
    OPEN_TRADES.append({"symbol": symbol, "side": side, "entry": entry, "tp": tp, "sl": sl})
    return f"🔥 SIGNAL\n{symbol} {side}\nEntry: {round(entry,4)}\nTP: {round(tp,4)}\nSL: {round(sl,4)}\nRR 1:{round(rr,2)}\nImpulse {round(impulse,2)}%"

def smart_money(symbol):
    k = get_klines(symbol, "15m")
    if not k: return None
    closes = [float(x[4]) for x in k]
    highs  = [float(x[2]) for x in k]
    lows   = [float(x[3]) for x in k]
    vol    = [float(x[5]) for x in k]
    if not is_strong_trend(closes): return None
    price, ma = closes[-1], sum(closes[-30:]) / 30
    trend = "LONG" if price > ma else "SHORT"
    impulse = (closes[-1] - closes[-5]) / closes[-5] * 100
    avg_vol = sum(vol[-20:]) / 20
    if vol[-1] > avg_vol * 2:
        if trend == "LONG":
            sl = min(lows[-20:]); tp = price + (price - sl) * 3
            return build_signal(symbol, "LONG", price, tp, sl, impulse)
        else:
            sl = max(highs[-20:]); tp = price - (sl - price) * 3
            return build_signal(symbol, "SHORT", price, tp, sl, impulse)

def impulse_detector(symbol):
    k = get_klines(symbol, "5m")
    if not k: return None
    closes = [float(x[4]) for x in k]
    vol = [float(x[5]) for x in k]
    price = closes[-1]
    impulse = (closes[-1] - closes[-3]) / closes[-3] * 100
    avg_vol = sum(vol[:-1]) / len(vol[:-1])
    if vol[-1] > avg_vol * 3 and abs(impulse) > MIN_IMPULSE:
        side = "LONG" if impulse > 0 else "SHORT"
        sl = price * (0.996 if side == "LONG" else 1.004)
        tp = price * (1.025 if side == "LONG" else 0.975)
        return build_signal(symbol, side, price, tp, sl, impulse)

# ================= TRACK =================
def track():
    while True:
        for t in OPEN_TRADES[:]:
            k = get_klines(t["symbol"], "1m")
            if not k: continue
            price = float(k[-1][4])
            if (t["side"] == "LONG" and price >= t["tp"]) or (t["side"] == "SHORT" and price <= t["tp"]):
                send(f"✅ TP {t['symbol']}")
                OPEN_TRADES.remove(t)
            elif (t["side"] == "LONG" and price <= t["sl"]) or (t["side"] == "SHORT" and price >= t["sl"]):
                send(f"❌ SL {t['symbol']}")
                OPEN_TRADES.remove(t)
        time.sleep(30)

# ================= MAIN =================
def run():
    send("🚀 BOT STARTED ON PYTHONANYWHERE")
    while True:
        try:
            symbols = get_symbols()
            for s in symbols:
                if s in COOLDOWN and time.time() - COOLDOWN[s] < COOLDOWN_TIME:
                    continue
                sig = smart_money(s) or impulse_detector(s)
                if sig:
                    send(sig)
                    COOLDOWN[s] = time.time()
                    break
        except Exception as e:
            print(f"Помилка в основному циклі: {e}")
        time.sleep(300)

if __name__ == "__main__":
    # На PythonAnywhere краще запускати track в окремому потоці, а run у головному
    threading.Thread(target=track, daemon=True).start()
    run()

import os
import requests
import time
import threading
import hashlib
import json as _json
from datetime import datetime
from flask import Flask
from threading import Thread

# ================= CONFIG (Береться з Railway Variables) =================

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

# ================= KEEP ALIVE (Для Railway) =================
app = Flask('')

@app.route('/')
def home():
    return "Bot is alive and running!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    Thread(target=run_web, daemon=True).start()

# ================= ENDPOINTS =================
BNC_KLINES = "https://api.binance.com/api/v3/klines"
BNC_TICKER_24H = "https://api.binance.com/api/v3/ticker/24hr"

# ================= SETTINGS =================
MIN_VOLUME = 50000000
MIN_IMPULSE = 3
MIN_RR = 3

# ================= STATE & ANTI-SPAM =================
COOLDOWN = {}
COOLDOWN_TIME = 3600
OPEN_TRADES = []
SIGNAL_CACHE = {}  # Для запобігання дублікатів
SIGNAL_TTL = 7200  # Час життя кешу сигналу (2 години)

# ================= TELEGRAM =================
def send(msg):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("Помилка: TELEGRAM_TOKEN або CHAT_ID не знайдено в налаштуваннях!")
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": CHAT_ID, "text": msg}, timeout=10)
    except Exception as e:
        print(f"Telegram error: {e}")

# ================= DATA FETCHING =================
def safe_get(url, params=None):
    try:
        r = requests.get(url, params=params, timeout=15)
        return r.json() if r.status_code == 200 else None
    except Exception as e:
        print(f"API error ({url}): {e}")
        return None

def get_symbols():
    data = safe_get(BNC_TICKER_24H)
    coins = []
    if not isinstance(data, list): return []
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

# ================= LOGIC & FILTRATION =================
def build_signal(symbol, side, entry, tp, sl, impulse):
    try:
        rr = abs((tp - entry) / (entry - sl))
    except: return None
    
    if rr < MIN_RR or abs(impulse) < MIN_IMPULSE: return None
    
    # Створення унікального ключа сигналу для фільтрації спаму
    signal_key = hashlib.md5(f"{symbol}_{side}_{round(entry, 2)}".encode()).hexdigest()
    
    now = time.time()
    # Якщо такий сигнал уже був надісланий нещодавно - ігноруємо
    if signal_key in SIGNAL_CACHE:
        if now - SIGNAL_CACHE[signal_key] < SIGNAL_TTL:
            return None
            
    SIGNAL_CACHE[signal_key] = now
    OPEN_TRADES.append({"symbol": symbol, "side": side, "entry": entry, "tp": tp, "sl": sl})
    
    return f"🔥 SIGNAL: {symbol} {side}\nEntry: {round(entry,4)}\nTP: {round(tp,4)}\nSL: {round(sl,4)}\nImpulse: {round(impulse,2)}%"

def smart_money(symbol):
    k = get_klines(symbol, "15m")
    if not k or len(k) < 30: return None
    closes = [float(x[4]) for x in k]
    lows = [float(x[3]) for x in k]
    highs = [float(x[2]) for x in k]
    vol = [float(x[5]) for x in k]
    
    price, ma = closes[-1], sum(closes[-30:]) / 30
    trend = "LONG" if price > ma else "SHORT"
    impulse = (closes[-1] - closes[-5]) / (closes[-5] or 1) * 100
    avg_vol = sum(vol[-20:]) / 20
    
    if vol[-1] > avg_vol * 2:
        if trend == "LONG":
            sl = min(lows[-20:]); tp = price + (price - sl) * 3
            return build_signal(symbol, "LONG", price, tp, sl, impulse)
        else:
            sl = max(highs[-20:]); tp = price - (sl - price) * 3
            return build_signal(symbol, "SHORT", price, tp, sl, impulse)
    return None

# ================= TRACKING & MONITORING =================
def track():
    while True:
        for t in OPEN_TRADES[:]:
            k = get_klines(t["symbol"], "1m")
            if not k: continue
            price = float(k[-1][4])
            if (t["side"] == "LONG" and price >= t["tp"]) or (t["side"] == "SHORT" and price <= t["tp"]):
                send(f"✅ PROFIT: {t['symbol']}")
                OPEN_TRADES.remove(t)
            elif (t["side"] == "LONG" and price <= t["sl"]) or (t["side"] == "SHORT" and price >= t["sl"]):
                send(f"❌ STOP LOSS: {t['symbol']}")
                OPEN_TRADES.remove(t)
        time.sleep(30)

# ================= MAIN RUN =================
def run():
    # Повідомлення про запуск тільки один раз при старті скрипта
    send("🚀 Бот успішно запущений та очікує сильних сигналів.")
    
    while True:
        try:
            symbols = get_symbols()
            for s in symbols:
                # Перевірка на внутрішній cooldown монети (1 година)
                if s in COOLDOWN and time.time() - COOLDOWN[s] < COOLDOWN_TIME:
                    continue
                
                sig = smart_money(s)
                if sig:
                    send(sig)
                    COOLDOWN[s] = time.time()
                    break # Перехід до наступного циклу очікування
        except Exception as e:
            print(f"Main loop error: {e}")
        time.sleep(300)

if __name__ == "__main__":
    keep_alive() # Запуск веб-сервера для Railway
    threading.Thread(target=track, daemon=True).start()
    run()

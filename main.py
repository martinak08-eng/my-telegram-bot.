import os
import requests
import time
import hashlib
import threading
from flask import Flask, request

# ================= CONFIG =================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

if not TELEGRAM_TOKEN or not CHAT_ID:
    raise Exception("❌ Немає TELEGRAM_TOKEN або CHAT_ID у змінних оточення")

app = Flask(__name__)

# ================= STATE =================
SIGNAL_CACHE = {}
SIGNAL_TTL = 7200  
LAST_SCAN = "Ще не було"
OPEN_TRADES = []

# ================= TELEGRAM SEND =================
def send(msg):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"}, timeout=10)
    except:
        pass

# ================= WEBHOOK (ОБРОБКА КОМАНД) =================
@app.route("/", methods=['GET', 'POST'])
def home():
    if request.method == 'POST':
        try:
            update = request.get_json()
            if "message" in update:
                text = update["message"].get("text", "")
                chat_id = update["message"]["chat"]["id"]

                # Перевірка, щоб бот відповідав тільки вам
                if str(chat_id) == str(CHAT_ID):
                    if text == "/check" or "статус" in text.lower():
                        send(f"✅ **BOT V2.1 ACTIVE**\n📊 Останній скан: {LAST_SCAN}\n📈 Активних сигналів: {len(OPEN_TRADES)}")
                    
                    elif text == "/version":
                        send(f"🤖 **Версія:** 2.1 PRO\n🚀 Режим: Webhook\nServer: Railway")
                    
                    elif "/trades" in text or "угоди" in text.lower():
                        if not OPEN_TRADES:
                            send("Немає активних угод")
                        else:
                            msg = "📈 **Активні угоди:**\n" + "\n".join([f"• {t['symbol']}" for t in OPEN_TRADES])
                            send(msg)
        except:
            pass
        return "ok", 200
    
    return "✅ BOT WORKING V2.1 (WEBHOOK MODE)", 200

# ================= АНТИ-ДУБЛІКАТ =================
def is_duplicate(symbol, side, entry):
    key = hashlib.md5(f"{symbol}_{side}_{round(entry,3)}".encode()).hexdigest()
    now = time.time()
    for k in list(SIGNAL_CACHE.keys()):
        if now - SIGNAL_CACHE[k] > SIGNAL_TTL:
            del SIGNAL_CACHE[k]
    if key in SIGNAL_CACHE:
        return True
    SIGNAL_CACHE[key] = now
    return False

# ================= BINANCE DATA =================
def get_all_symbols():
    try:
        data = requests.get("https://api.binance.com/api/v3/ticker/24hr", timeout=10).json()
        coins = [c["symbol"] for c in data if c["symbol"].endswith("USDT") and float(c["quoteVolume"]) > 20000000]
        return coins[:50]
    except:
        return []

def analyze(symbol):
    try:
        k = requests.get("https://api.binance.com/api/v3/klines", 
                         params={"symbol": symbol, "interval": "5m", "limit": 50}, timeout=10).json()
        closes = [float(x[4]) for x in k]
        highs = [float(x[2]) for x in k]
        lows = [float(x[3]) for x in k]
        volume = [float(x[5]) for x in k]
        price = closes[-1]

        ma = sum(closes[-20:]) / 20
        trend = "LONG" if price > ma else "SHORT"
        impulse = (closes[-1] - closes[-5]) / closes[-5] * 100
        avg_vol = sum(volume[:-1]) / len(volume[:-1])
        spike = volume[-1] > avg_vol * 2
        
        sweep_high = price >= max(highs[-20:])
        sweep_low = price <= min(lows[-20:])

        if trend == "LONG" and sweep_low and spike and impulse > 1.5:
            sl = min(lows[-20:])
            tp = price + (price - sl) * 3
            if not is_duplicate(symbol, "LONG", price):
                return build_signal(symbol, "LONG", price, tp, sl, impulse)

        if trend == "SHORT" and sweep_high and spike and impulse < -1.5:
            sl = max(highs[-20:])
            tp = price - (sl - price) * 3
            if not is_duplicate(symbol, "SHORT", price):
                return build_signal(symbol, "SHORT", price, tp, sl, impulse)
    except:
        return None

def build_signal(symbol, side, entry, tp, sl, impulse):
    text = f"🚀 **SIGNAL {symbol}**\nSide: {side}\nEntry: {round(entry,4)}\nTP: {round(tp,4)}\nSL: {round(sl,4)}\nImpulse: {round(impulse,2)}%"
    OPEN_TRADES.append({"symbol": symbol, "side": side})
    return text

# ================= MARKET LOOP =================
def market_loop():
    global LAST_SCAN
    time.sleep(5) # Даємо серверу запуститися
    send("✅ **BOT V2.1 STARTED**\nСканування ринку запущено.")
    while True:
        try:
            symbols = get_all_symbols()
            for s in symbols:
                signal = analyze(s)
                if signal:
                    send(signal)
            LAST_SCAN = time.strftime("%H:%M:%S")
        except Exception as e:
            print(f"Loop error: {e}")
        time.sleep(300)

# ================= MAIN =================
if __name__ == "__main__":
    # Запуск сканера в окремому потоці
    threading.Thread(target=market_loop, daemon=True).start()
    
    # Запуск Flask сервера
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

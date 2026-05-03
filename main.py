import os
import requests
import time
import threading
from flask import Flask, request

# --- НАЛАШТУВАННЯ ---
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
BOT_VERSION = "2.5 PRO (Stable)"

app = Flask(__name__)

# --- СТАН БОТА ---
OPEN_TRADES = []
SYMBOL_COOLDOWN = {}
SYMBOL_BLOCK_TIME = 3600

# --- СИСТЕМНІ ФУНКЦІЇ ---
def send_msg(msg):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"}, timeout=10)
    except:
        pass

# --- ОБРОБКА КОМАНД (WEBHOOK) ---
@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        update = request.get_json()
        if update and "message" in update:
            chat_id = str(update["message"]["chat"]["id"])
            text = update["message"].get("text", "").lower()

            # Реагуємо на текст (кнопки)
            if "/version" in text:
                send_msg(f"⚙️ **Версія:** {BOT_VERSION}\n💎 Моніторинг: АКТИВНО\n📡 API: СТАБІЛЬНЕ\n🚀 Режим: SMART SCAN")
            
            elif "статус" in text:
                send_msg(f"📊 **Статус:**\n✅ Бот працює\n📈 Сигналів у пам'яті: {len(OPEN_TRADES)}")
            
            elif "угоди" in text:
                if not OPEN_TRADES:
                    send_msg("💼 **Портфель:**\nНаразі активних сигналів немає.")
                else:
                    msg = "📈 **Активні угоди:**\n" + "\n".join([f"• {t['symbol']} ({t['side']})" for t in OPEN_TRADES])
                    send_msg(msg)
            
            elif "watchlist" in text:
                send_msg("🔎 **Watchlist:** Скан Binance ТОП-об'ємів активний. Очікуйте сигнал...")

    except Exception as e:
        print(f"Помилка логіки: {e}")
    return "ok", 200

@app.route('/')
def index():
    return f"Bot {BOT_VERSION} is online!", 200

# --- ЛОГІКА СКАНЕРА BINANCE ---
def scan_market():
    while True:
        try:
            # Отримуємо дані з Binance
            res = requests.get("https://api.binance.com/api/v3/ticker/24hr", timeout=10).json()
            tickers = [c for c in res if c["symbol"].endswith("USDT") and float(c["quoteVolume"]) > 50000000]
            
            for t in tickers:
                symbol = t["symbol"]
                change = float(t["priceChangePercent"])
                
                # Логіка сигналу: зміна ціни більше 5%
                if abs(change) > 5.0:
                    now = time.time()
                    if symbol not in SYMBOL_COOLDOWN or (now - SYMBOL_COOLDOWN[symbol] > SYMBOL_BLOCK_TIME):
                        side = "LONG 📈" if change > 0 else "SHORT 📉"
                        price = t["lastPrice"]
                        msg = f"🔥 **SIGNAL: {symbol}**\nНапрямок: {side}\nЦіна: {price}\nЗміна: {change}%"
                        send_msg(msg)
                        
                        SYMBOL_COOLDOWN[symbol] = now
                        OPEN_TRADES.append({"symbol": symbol, "side": side})
            
            time.sleep(300) # Перевірка кожні 5 хв
        except:
            time.sleep(60)

# --- ЗАПУСК ---
if __name__ == "__main__":
    # 1. Запуск сканера у фоновому потоці
    threading.Thread(target=scan_market, daemon=True).start()
    
    # 2. Запуск сервера (Railway сам надає PORT)
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

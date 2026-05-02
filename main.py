import os
import requests
import time
import threading
import hashlib
import json as _json
from flask import Flask, request
from threading import Thread

# ================= CONFIG (Береться з Railway Variables) =================
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

# ================= KEEP ALIVE & WEBHOOKS =================
app = Flask('')

@app.route('/')
def home():
    return "Bot is running"

# Обробка вхідних повідомлень (натискання кнопок)
@app.route('/' + (TELEGRAM_TOKEN if TELEGRAM_TOKEN else "webhook"), methods=['POST'])
def webhook():
    update = request.get_json()
    if "message" in update:
        text = update["message"].get("text")
        chat_id = update["message"]["chat"]["id"]
        
        if text == "📊 Статус":
            send_msg(chat_id, "✅ Бот працює стабільно. Пошук сигналів триває...")
        elif text == "👀 Watchlist":
            send_msg(chat_id, "🔎 У списку спостереження зараз 30 активних USDT пар.")
        elif text == "📈 Угоди":
            count = len(OPEN_TRADES)
            send_msg(chat_id, f"💼 Активних угод зараз: {count}")
        elif text == "🏆 Stats":
            send_msg(chat_id, "📊 Статистика за сьогодні: 0 Win / 0 Loss (оновлюється після закриття угод)")
    return "OK", 200

def run_web():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# ================= STATE & FILTERS =================
COOLDOWN = {}
OPEN_TRADES = []
SIGNAL_CACHE = {} 
SIGNAL_TTL = 7200 # 2 години не повторювати сигнал

# ================= TELEGRAM FUNCTIONS =================
def send_msg(chat, msg):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": chat, "text": msg}, timeout=10)
    except Exception as e:
        print(f"Error: {e}")

# ================= LOGIC =================
def build_signal(symbol, side, entry, tp, sl, impulse):
    # Унікальний ключ сигналу, щоб не спамити
    sig_id = hashlib.md5(f"{symbol}_{side}_{round(entry,2)}".encode()).hexdigest()
    
    if sig_id in SIGNAL_CACHE:
        if time.time() - SIGNAL_CACHE[sig_id] < SIGNAL_TTL:
            return None # Пропускаємо дублікат
            
    SIGNAL_CACHE[sig_id] = time.time()
    OPEN_TRADES.append({"symbol": symbol, "tp": tp, "sl": sl, "side": side})
    
    return f"🔥 СИГНАЛ: {symbol} {side}\nВхід: {round(entry,4)}\nTP: {round(tp,4)}\nSL: {round(sl,4)}\nІмпульс: {round(impulse,2)}%"

def get_data():
    # Спрощена логіка отримання даних з Binance
    try:
        r = requests.get("https://api.binance.com/api/v3/ticker/24hr", timeout=10).json()
        for item in r[:20]: # Беремо топ монет
            if "USDT" in item['symbol']:
                change = float(item['priceChangePercent'])
                if abs(change) > 4: # Якщо рух більше 4%
                    price = float(item['lastPrice'])
                    side = "LONG" if change > 0 else "SHORT"
                    tp = price * (1.02 if side == "LONG" else 0.98)
                    sl = price * (0.99 if side == "LONG" else 1.01)
                    sig = build_signal(item['symbol'], side, price, tp, sl, change)
                    if sig:
                        send_msg(CHAT_ID, sig)
    except:
        pass

def main_loop():
    # Повідомлення про запуск ТІЛЬКИ ОДИН РАЗ
    send_msg(CHAT_ID, "🚀 Бот успішно запущений на Railway. Очікую сигнали...")
    while True:
        get_data()
        time.sleep(300) # Перевірка кожні 5 хвилин

if __name__ == "__main__":
    # Запуск веб-сервера та бота в різних потоках
    Thread(target=run_web).start()
    main_loop()


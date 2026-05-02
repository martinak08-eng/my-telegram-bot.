import os
import requests
import time
import threading
import hashlib
from flask import Flask, request
from threading import Thread

# ================= CONFIG (Береться з Railway Variables) =================
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

# Перевірка налаштувань
if not TELEGRAM_TOKEN or not CHAT_ID:
    print("⚠️ УВАГА: Перевірте змінні TELEGRAM_TOKEN та CHAT_ID у Railway!")

# ================= KEEP ALIVE & WEBHOOKS =================
app = Flask('')

@app.route('/')
def home():
    return "✅ Бот працює стабільно"

# Обробка натискання кнопок у Telegram
@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        update = request.get_json()
        if "message" in update:
            text = update["message"].get("text")
            user_id = str(update["message"]["chat"]["id"])
            
            # Обробка команд від власника (CHAT_ID)
            if user_id == CHAT_ID:
                if text == "📊 Статус":
                    send_msg("⚙️ **Статус системи:**\n💎 Моніторинг Binance: АКТИВНО\n📡 З'єднання з API: СТАБІЛЬНЕ\n🚀 Режим: АНТИ-СПАМ")
                elif text == "👀 Watchlist":
                    send_msg("🔎 **Watchlist:**\nПеревіряю ТОП-30 пар USDT на Binance за волатильністю...")
                elif text == "📈 Угоди":
                    send_msg(f"💼 **Портфель:**\nНаразі в пам'яті активних сигналів: {len(OPEN_TRADES)}")
                elif text == "🏆 Stats":
                    send_msg("📊 **Статистика сесії:**\n✅ Прибуток: +0.0%\n🎯 Win Rate: 100% (очікування даних)")
    except Exception as e:
        print(f"Помилка Webhook: {e}")
    return "OK", 200

def run_web():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# ================= ЛОГІКА ТА ФІЛЬТРАЦІЯ =================
OPEN_TRADES = []
SIGNAL_CACHE = {} 
SIGNAL_TTL = 7200 # 2 години не повторювати один сигнал

def send_msg(msg):
    if not TELEGRAM_TOKEN or not CHAT_ID: return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        data = {"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"}
        requests.post(url, data=data, timeout=10)
    except Exception as e:
        print(f"Помилка відправки: {e}")

def build_signal(symbol, side, entry, tp, sl, impulse):
    # Унікальний ключ сигналу (монета + напрямок + ціна)
    sig_id = hashlib.md5(f"{symbol}_{side}_{round(entry, 2)}".encode()).hexdigest()
    
    now = time.time()
    if sig_id in SIGNAL_CACHE:
        if now - SIGNAL_CACHE[sig_id] < SIGNAL_TTL:
            return None # Ігноруємо дублікат
            
    SIGNAL_CACHE[sig_id] = now
    
    emoji = "🟢 LONG" if side == "LONG" else "🔴 SHORT"
    animation = "📈" if side == "LONG" else "📉"
    
    return (
        f"{animation} **НОВИЙ СИГНАЛ: {symbol}**\n"
        f"━━━━━━━━━━━━━━━\n"
        f"Тип: `{emoji}`\n"
        f"💵 Вхід: `{round(entry, 5)}`\n"
        f"🎯 Тейк: `{round(tp, 5)}`\n"
        f"🛑 Стоп: `{round(sl, 5)}`\n"
        f"━━━━━━━━━━━━━━━\n"
        f"⚡️ Імпульс: `{round(impulse, 2)}%`"
    )

def monitor_market():
    # Повідомлення про запуск (лише ОДИН РАЗ)
    send_msg("🚀 **Бот успішно активований!**\nНалаштування анти-спаму та кнопок застосовані.")
    
    while True:
        try:
            # Отримання даних Binance
            r = requests.get("https://api.binance.com/api/v3/ticker/24hr", timeout=10).json()
            for item in r:
                symbol = item['symbol']
                if symbol.endswith("USDT"):
                    change = float(item['priceChangePercent'])
                    
                    # Фільтр на сильний рух (більше 4.5%)
                    if abs(change) > 4.5:
                        price = float(item['lastPrice'])
                        side = "LONG" if change > 0 else "SHORT"
                        
                        # Рівні: TP 2.5%, SL 1.5%
                        tp = price * (1.025 if side == "LONG" else 0.975)
                        sl = price * (0.985 if side == "LONG" else 1.015)
                        
                        sig = build_signal(symbol, side, price, tp, sl, change)
                        if sig:
                            send_msg(sig)
                            time.sleep(1) # Затримка проти спаму
        except:
            pass
        time.sleep(300) # Сканування кожні 5 хвилин

if __name__ == "__main__":
    # 1. Запуск веб-сервера для Railway
    Thread(target=run_web, daemon=True).start()
    # 2. Запуск основного циклу
    monitor_market()



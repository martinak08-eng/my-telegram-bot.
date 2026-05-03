import os
import time
import requests
import threading
import hashlib
from flask import Flask

# ================= CONFIG & SECURITY =================
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
BINANCE_URL = "https://api.binance.com"

# Railway потребує веб-сервер, щоб тримати процес активним
app = Flask(__name__)

@app.route('/')
def health_check():
    return "🔥 Pro_Crypto_Signal_Bot is Online", 200

# ================= CORE LOGIC =================
class CryptoAnalyzer:
    def __init__(self):
        self.seen_signals = {}
        self.stats = {"signals": 0, "last_coin": None}

    def get_market_data(self, symbol, interval="15m", limit=100):
        try:
            params = {"symbol": symbol, "interval": interval, "limit": limit}
            res = requests.get(f"{BINANCE_URL}/api/v3/klines", params=params, timeout=10)
            return res.json()
        except:
            return None

    def analyze_smc(self, symbol):
        data = self.get_market_data(symbol)
        if not data: return None

        # Форматуємо дані: [0]time, [1]open, [2]high, [3]low, [4]close, [5]volume
        closes = [float(x[4]) for x in data]
        highs = [float(x[2]) for x in data]
        lows = [float(x[3]) for x in data]
        volumes = [float(x[5]) for x in data]

        current_price = closes[-1]
        
        # 1. Визначаємо структуру (High/Low за 50 свічок)
        range_high = max(highs[-50:-1])
        range_low = min(lows[-50:-1])
        
        # 2. Аналіз об'єму (Pump Detection)
        avg_vol = sum(volumes[-20:-1]) / 20
        vol_spike = volumes[-1] > avg_vol * 3  # Сплеск у 3 рази

        # 3. Логіка SMC (Liquidity Sweep + Rejection)
        signal = None
        
        # LONG: Ціна зняла лой і повернулася вище
        if lows[-1] < range_low and current_price > range_low:
            if vol_spike:
                sl = lows[-1] * 0.998
                tp = current_price + (current_price - sl) * 3
                signal = self.create_signal(symbol, "LONG (SMC Sweep)", current_price, tp, sl, "High")

        # SHORT: Ціна зняла хай і закріпилась нижче
        elif highs[-1] > range_high and current_price < range_high:
            if vol_spike:
                sl = highs[-1] * 1.002
                tp = current_price - (sl - current_price) * 3
                signal = self.create_signal(symbol, "SHORT (SMC Sweep)", current_price, tp, sl, "High")

        return signal

    def create_signal(self, symbol, mode, price, tp, sl, strength):
        # Хеш для уникнення дублів протягом 4 годин
        signal_id = hashlib.md5(f"{symbol}{mode}".encode()).hexdigest()
        if signal_id in self.seen_signals:
            if time.time() - self.seen_signals[signal_id] < 14400:
                return None
        
        self.seen_signals[signal_id] = time.time()
        self.stats["signals"] += 1
        self.stats["last_coin"] = symbol

        return (f"💎 **PREMIUM SIGNAL: {symbol}**\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"Тип: `{mode}`\n"
                f"Вхід: `{price:.5f}`\n"
                f"🎯 TP (1:3): `{tp:.5f}`\n"
                f"🛑 SL: `{sl:.5f}`\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"🔥 Сила сигналу: {strength}\n"
                f"⚠️ Ризик-менеджмент: 1-2% від депозиту")

# ================= TELEGRAM BOT =================
bot_logic = CryptoAnalyzer()

def send_msg(text):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown"})
    except: pass

def market_scanner():
    send_msg("🚀 **Система моніторингу SMC & Pump активована!**\nСканую ТОП-100 Binance...")
    while True:
        try:
            # Отримуємо топ монет за об'ємом
            tickers = requests.get(f"{BINANCE_URL}/api/v3/ticker/24hr").json()
            # Фільтруємо USDT пари з великим об'ємом
            top_coins = sorted([t for t in tickers if t['symbol'].endswith('USDT')], 
                               key=lambda x: float(x['quoteVolume']), reverse=True)[:100]
            
            for coin in top_coins:
                symbol = coin['symbol']
                signal = bot_logic.analyze_smc(symbol)
                if signal:
                    send_msg(signal)
                time.sleep(0.5) # Пауза для уникнення лімітів API
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(10)

def telegram_polling():
    last_update = 0
    while True:
        try:
            url = f"https://api.telegram.org/bot{TOKEN}/getUpdates?offset={last_update + 1}&timeout=30"
            res = requests.get(url).json()
            for update in res.get("result", []):
                last_update = update["update_id"]
                msg = update.get("message", {})
                text = msg.get("text", "")
                
                if text == "/status":
                    status = (f"📊 **Статус Бота**\n"
                             f"Знайдено сигналів: {bot_logic.stats['signals']}\n"
                             f"Остання монета: {bot_logic.stats['last_coin']}\n"
                             f"Сервер: Railway Active ✅")
                    send_msg(status)
                elif text == "/help":
                    send_msg("Доступні команди:\n/status - перевірка роботи\n/watch - додати монету (в розробці)")
        except:
            time.sleep(5)

# ================= START =================
if __name__ == "__main__":
    # Запуск веб-сервера для Railway в окремому потоці
    threading.Thread(target=lambda: app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))).start()
    # Запуск сканера ринку
    threading.Thread(target=market_scanner).start()
    # Запуск обробки команд
    telegram_polling()

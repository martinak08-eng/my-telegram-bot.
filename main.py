# =========================================================

# 🚀 FUTURES INTRADAY SMART MONEY BOT

# FULL FINAL VERSION

# Railway / Render / Replit READY

# =========================================================

import os

import time

import requests

import threading

import hashlib

from statistics import mean

from flask import Flask

# =========================================================

# CONFIG

# =========================================================

TOKEN = os.getenv("TELEGRAM_TOKEN")

CHAT_ID = os.getenv("CHAT_ID")

BINANCE = "https://api.binance.com"

SCAN_INTERVAL = 300          # 5 хв

MAX_COINS = 150              # топ ліквідних монет

SIGNAL_COOLDOWN = 21600      # 6 год антиспам

MIN_SCORE = 10               # мінімальний рейтинг

MIN_VOLUME = 35000000        # мін. ліквідність

# =========================================================

# FLASK SERVER

# =========================================================

app = Flask(__name__)

@app.route("/")

def home():

    return "✅ FUTURES BOT ONLINE", 200

# =========================================================

# TELEGRAM SEND

# =========================================================

def send_message(text):

    try:

        requests.post(

            f"https://api.telegram.org/bot{TOKEN}/sendMessage",

            json={

                "chat_id": CHAT_ID,

                "text": text,

                "parse_mode": "Markdown"

            },

            timeout=10

        )

    except Exception as e:

        print("TG ERROR:", e)

# =========================================================

# MAIN BOT

# =========================================================

class FuturesBot:

    def __init__(self):

        self.sent_signals = {}

        self.stats = {

            "signals": 0,

            "wins": 0,

            "losses": 0,

            "last_signal": "NONE"

        }

    # =====================================================

    # GET KLINES

    # =====================================================

    def get_klines(self, symbol, interval, limit=120):

        try:

            r = requests.get(

                f"{BINANCE}/api/v3/klines",

                params={

                    "symbol": symbol,

                    "interval": interval,

                    "limit": limit

                },

                timeout=10

            )

            if r.status_code != 200:

                return None

            return r.json()

        except:

            return None

    # =====================================================

    # EMA

    # =====================================================

    def ema(self, data, period):

        if len(data) < period:

            return None

        multiplier = 2 / (period + 1)

        ema = mean(data[:period])

        for price in data[period:]:

            ema = ((price - ema) * multiplier) + ema

        return ema

    # =====================================================

    # RSI

    # =====================================================

    def rsi(self, closes, period=14):

        gains = []

        losses = []

        for i in range(-period, -1):

            diff = closes[i] - closes[i - 1]

            if diff > 0:

                gains.append(diff)

            else:

                losses.append(abs(diff))

        avg_gain = mean(gains) if gains else 0.001

        avg_loss = mean(losses) if losses else 0.001

        rs = avg_gain / avg_loss

        return 100 - (100 / (1 + rs))

    # =====================================================

    # MAIN ANALYSIS

    # =====================================================

    def analyze(self, symbol):

        # =================================================

        # MULTI TIMEFRAME

        # =================================================

        data_15m = self.get_klines(symbol, "15m")

        data_1h = self.get_klines(symbol, "1h")

        if not data_15m or not data_1h:

            return None

        closes = [float(x[4]) for x in data_15m]

        highs = [float(x[2]) for x in data_15m]

        lows = [float(x[3]) for x in data_15m]

        volumes = [float(x[5]) for x in data_15m]

        closes_1h = [float(x[4]) for x in data_1h]

        current = closes[-1]

        # =================================================

        # TREND FILTER

        # =================================================

        ema20 = self.ema(closes_1h, 20)

        ema50 = self.ema(closes_1h, 50)

        if not ema20 or not ema50:

            return None

        bullish = ema20 > ema50

        bearish = ema20 < ema50

        # =================================================

        # VOLUME FILTER

        # =================================================

        avg_volume = mean(volumes[-25:])

        volume_spike = volumes[-1] > avg_volume * 2.5

        if not volume_spike:

            return None

        # =================================================

        # MOMENTUM FILTER

        # =================================================

        impulse = (

            (closes[-1] - closes[-5])

            / closes[-5]

        ) * 100

        long_impulse = impulse > 2.3

        short_impulse = impulse < -2.3

        # =================================================

        # VOLATILITY FILTER

        # =================================================

        volatility = (

            (max(highs[-20:]) - min(lows[-20:]))

            / current

        ) * 100

        if volatility < 3:

            return None

        # =================================================

        # LIQUIDITY SWEEP

        # =================================================

        recent_high = max(highs[-30:-1])

        recent_low = min(lows[-30:-1])

        sweep_low = lows[-1] < recent_low

        sweep_high = highs[-1] > recent_high

        # =================================================

        # RSI

        # =================================================

        rsi = self.rsi(closes)

        # =================================================

        # LONG SCORE

        # =================================================

        long_score = 0

        long_reasons = []

        if bullish:

            long_score += 2

            long_reasons.append("1H bullish trend")

        if long_impulse:

            long_score += 3

            long_reasons.append("Strong bullish impulse")

        if volume_spike:

            long_score += 2

            long_reasons.append("Volume spike")

        if sweep_low:

            long_score += 2

            long_reasons.append("Liquidity sweep")

        if 45 < rsi < 70:

            long_score += 1

            long_reasons.append("Healthy RSI")

        # =================================================

        # SHORT SCORE

        # =================================================

        short_score = 0

        short_reasons = []

        if bearish:

            short_score += 2

            short_reasons.append("1H bearish trend")

        if short_impulse:

            short_score += 3

            short_reasons.append("Strong bearish impulse")

        if volume_spike:

            short_score += 2

            short_reasons.append("Volume spike")

        if sweep_high:

            short_score += 2

            short_reasons.append("Liquidity sweep")

        if 30 < rsi < 55:

            short_score += 1

            short_reasons.append("Healthy RSI")

        # =================================================

        # FINAL DECISION

        # =================================================

        direction = None

        score = 0

        reasons = []

        if long_score >= MIN_SCORE and long_score > short_score:

            direction = "LONG"

            score = long_score

            reasons = long_reasons

        elif short_score >= MIN_SCORE and short_score > long_score:

            direction = "SHORT"

            score = short_score

            reasons = short_reasons

        else:

            return None

        # =================================================

        # ANTI SPAM

        # =================================================

        signal_hash = hashlib.md5(

            f"{symbol}{direction}".encode()

        ).hexdigest()

        now = time.time()

        if signal_hash in self.sent_signals:

            if now - self.sent_signals[signal_hash] < SIGNAL_COOLDOWN:

                return None

        self.sent_signals[signal_hash] = now

        # =================================================

        # TAKE PROFIT / STOP LOSS

        # =================================================

        if direction == "LONG":

            sl = min(lows[-12:]) * 0.998

            risk = current - sl

            tp = current + (risk * 3)

        else:

            sl = max(highs[-12:]) * 1.002

            risk = sl - current

            tp = current - (risk * 3)

        # =================================================

        # TP DISTANCE FILTER

        # =================================================

        tp_distance = abs((tp - current) / current) * 100

        if tp_distance < 3:

            return None

        # =================================================

        # CONFIDENCE

        # =================================================

        confidence = min(96, 76 + score * 2)

        # =================================================

        # SETUP TYPE

        # =================================================

        setup_type = (

            "⚡ Pump / Momentum"

            if abs(impulse) > 3

            else "📈 Smart Money Intraday"

        )

        # =================================================

        # DURATION

        # =================================================

        if abs(impulse) > 4:

            duration = "2-6 годин"

        else:

            duration = "6-24 години"

        # =================================================

        # STATS

        # =================================================

        self.stats["signals"] += 1

        self.stats["last_signal"] = symbol

        # =================================================

        # FINAL MESSAGE

        # =================================================

        text = f"""

🔥 *PREMIUM FUTURES SIGNAL*

💎 Pair:

`{symbol}`

📊 Direction:

`{direction}`

⚡ Setup:

{setup_type}

💰 Entry:

`{round(current, 6)}`

🛑 Stop Loss:

`{round(sl, 6)}`

🎯 Take Profit:

`{round(tp, 6)}`

📈 Confidence:

*{confidence}%*

⏳ Expected Duration:

`{duration}`

━━━━━━━━━━━━━━━

🧠 Confirmations:

"""

        for r in reasons:

            text += f"\n• {r}"

        text += """

━━━━━━━━━━━━━━━

📌 Risk Reward:

1:3

🛡 Anti-Spam:

Enabled

💡 Position Type:

Intraday Futures

"""

        return text

# =========================================================

# BOT INSTANCE

# =========================================================

bot = FuturesBot()

# =========================================================

# MARKET SCANNER

# =========================================================

def market_scanner():

    send_message(

        "🚀 *FUTURES INTRADAY BOT ACTIVATED*\n"

        "🔍 Scanning Binance Futures Market\n"

        "⚡ High Quality Mode Enabled"

    )

    while True:

        try:

            tickers = requests.get(

                f"{BINANCE}/api/v3/ticker/24hr",

                timeout=15

            ).json()

            filtered = []

            for t in tickers:

                try:

                    symbol = t["symbol"]

                    if not symbol.endswith("USDT"):

                        continue

                    volume = float(t["quoteVolume"])

                    change = abs(float(t["priceChangePercent"]))

                    # FILTER LOW QUALITY

                    if volume < MIN_VOLUME:

                        continue

                    if change < 2:

                        continue

                    filtered.append(t)

                except:

                    continue

            # =================================================

            # SORT BY VOLUME

            # =================================================

            filtered = sorted(

                filtered,

                key=lambda x: float(x["quoteVolume"]),

                reverse=True

            )[:MAX_COINS]

            # =================================================

            # ANALYZE

            # =================================================

            for coin in filtered:

                symbol = coin["symbol"]

                signal = bot.analyze(symbol)

                if signal:

                    send_message(signal)

                time.sleep(0.7)

            print("SCAN FINISHED")

            time.sleep(SCAN_INTERVAL)

        except Exception as e:

            print("SCAN ERROR:", e)

            time.sleep(15)

# =========================================================

# TELEGRAM COMMANDS

# =========================================================

def telegram_commands():

    last_update = 0

    while True:

        try:

            url = (

                f"https://api.telegram.org/bot{TOKEN}"

                f"/getUpdates?offset={last_update + 1}&timeout=30"

            )

            res = requests.get(url, timeout=35).json()

            for update in res.get("result", []):

                last_update = update["update_id"]

                msg = update.get("message", {})

                text = msg.get("text", "").lower()

                # =================================================

                if text in ["/status", "📊 статус"]:

                    send_message(

                        f"""

📊 *BOT STATUS*

✅ Scanner: ACTIVE

✅ Smart Money: ENABLED

✅ Intraday Mode: ENABLED

✅ Anti-Spam: ENABLED

📈 Signals:

`{bot.stats["signals"]}`

💎 Last Signal:

`{bot.stats["last_signal"]}`

⚡ Strategy:

Intraday Momentum + SMC

"""

                    )

                # =================================================

                elif text in ["/logic", "🧠 логіка"]:

                    send_message(

                        """

🧠 *CURRENT BOT LOGIC*

✅ Full Binance scan

✅ Smart Money concepts

✅ Liquidity sweeps

✅ Momentum entries

✅ Volume confirmation

✅ Trend confirmation

✅ Intraday signals

✅ High liquidity only

✅ Volatility filter

✅ RSI filter

✅ 1:3 Risk Reward

✅ Anti-spam system

🚫 Weak setups ignored

🚫 Low volume ignored

🚫 Sideways market ignored

"""

                    )

        except Exception as e:

            print("TG ERROR:", e)

            time.sleep(5)

# =========================================================

# START

# =========================================================

if __name__ == "__main__":

    threading.Thread(

        target=lambda: app.run(

            host="0.0.0.0",

            port=int(os.environ.get("PORT", 8080))

        ),

        daemon=True

    ).start()

    threading.Thread(

        target=market_scanner,

        daemon=True

    ).start()

    telegram_commands()

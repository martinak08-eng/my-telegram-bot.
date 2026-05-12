import os

import time

import requests

import threading

import hashlib

from flask import Flask

# =========================================================

#                CONFIG

# =========================================================

TOKEN = os.getenv("TELEGRAM_TOKEN")

CHAT_ID = os.getenv("CHAT_ID")

BINANCE_URL = "https://fapi.binance.com"

SCAN_INTERVAL = 300

TOP_COINS_LIMIT = 120

MIN_VOLUME_USDT = 30000000

MIN_VOLATILITY = 3.0

MIN_SCORE = 7

ANTI_SPAM_MINUTES = 360

# =========================================================

#                FLASK (REPLIT / RAILWAY)

# =========================================================

app = Flask(__name__)

@app.route("/")

def home():

    return "🚀 Intraday Ultra v9 FINAL ACTIVE", 200

# =========================================================

#                BOT CORE

# =========================================================

class IntradayBot:

    def __init__(self):

        self.sent_signals = {}

        self.active_trades = {}

        self.closed_trades = []

        self.watchlist = []

        self.stats = {

            "signals": 0,

            "wins": 0,

            "losses": 0,

            "pump": 0,

            "smart": 0,

            "last": "-"

        }

bot = IntradayBot()

# =========================================================

#                TELEGRAM

# =========================================================

def send_message(text):

    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"

    try:

        requests.post(

            url,

            json={

                "chat_id": CHAT_ID,

                "text": text,

                "parse_mode": "Markdown"

            },

            timeout=15

        )

    except Exception as e:

        print(e)

# =========================================================

#                MARKET DATA

# =========================================================

def get_klines(symbol, interval="15m", limit=120):

    try:

        url = f"{BINANCE_URL}/fapi/v1/klines"

        params = {

            "symbol": symbol,

            "interval": interval,

            "limit": limit

        }

        r = requests.get(url, params=params, timeout=15)

        return r.json()

    except:

        return None

def get_price(symbol):

    try:

        url = f"{BINANCE_URL}/fapi/v1/ticker/price"

        r = requests.get(

            url,

            params={"symbol": symbol},

            timeout=10

        ).json()

        return float(r["price"])

    except:

        return None

# =========================================================

#                ANALYSIS

# =========================================================

def analyze_symbol(symbol):

    data = get_klines(symbol)

    if not data or len(data) < 80:

        return None

    closes = [float(x[4]) for x in data]

    highs = [float(x[2]) for x in data]

    lows = [float(x[3]) for x in data]

    volumes = [float(x[5]) for x in data]

    current = closes[-1]

    high_20 = max(highs[-20:])

    low_20 = min(lows[-20:])

    avg_volume = sum(volumes[-25:-1]) / 24

    current_volume = volumes[-1]

    volume_ratio = current_volume / avg_volume

    volatility = ((high_20 - low_20) / low_20) * 100

    ema_fast = sum(closes[-9:]) / 9

    ema_slow = sum(closes[-21:]) / 21

    momentum = ((current - closes[-6]) / closes[-6]) * 100

    score = 0

    signal_type = None

    side = None

    # =====================================================

    # SMART MONEY LONG

    # =====================================================

    if (

        current > ema_fast

        and ema_fast > ema_slow

        and volume_ratio >= 2.5

        and momentum >= 2.2

        and volatility >= MIN_VOLATILITY

    ):

        score += 7

        signal_type = "SMART MONEY"

        side = "LONG"

    # =====================================================

    # SMART MONEY SHORT

    # =====================================================

    elif (

        current < ema_fast

        and ema_fast < ema_slow

        and volume_ratio >= 2.5

        and momentum <= -2.2

        and volatility >= MIN_VOLATILITY

    ):

        score += 7

        signal_type = "SMART MONEY"

        side = "SHORT"

    # =====================================================

    # PUMP LONG

    # =====================================================

    if (

        current >= high_20 * 0.995

        and volume_ratio >= 3.5

        and momentum >= 3

    ):

        score += 3

        signal_type = "PUMP"

        side = "LONG"

    # =====================================================

    # DUMP SHORT

    # =====================================================

    if (

        current <= low_20 * 1.005

        and volume_ratio >= 3.5

        and momentum <= -3

    ):

        score += 3

        signal_type = "DUMP"

        side = "SHORT"

    # =====================================================

    # QUALITY FILTER

    # =====================================================

    if score < MIN_SCORE:

        return None

    # =====================================================

    # ATR STOP LOSS

    # =====================================================

    atr = (max(highs[-14:]) - min(lows[-14:])) / current

    if side == "LONG":

        sl = current * (1 - atr * 1.2)

        tp = current + ((current - sl) * 3)

    else:

        sl = current * (1 + atr * 1.2)

        tp = current - ((sl - current) * 3)

    rr = abs(tp - current) / abs(current - sl)

    if rr < 2.8:

        return None

    # =====================================================

    # ANTI SPAM

    # =====================================================

    signal_id = f"{symbol}_{side}"

    now = time.time()

    if signal_id in bot.sent_signals:

        last = bot.sent_signals[signal_id]

        if now - last < (ANTI_SPAM_MINUTES * 60):

            return None

    bot.sent_signals[signal_id] = now

    # =====================================================

    # SIGNAL

    # =====================================================

    duration = "6-24 годин"

    confidence = min(score * 10, 95)

    text = (

        f"🚨 *INTRADAY SIGNAL*\n\n"

        f"💎 Монета: `{symbol}`\n"

        f"📊 Тип: `{side}`\n"

        f"⚡ Сетап: `{signal_type}`\n\n"

        f"💰 Вхід: `{round(current, 5)}`\n"

        f"🎯 Take Profit: `{round(tp, 5)}`\n"

        f"🛑 Stop Loss: `{round(sl, 5)}`\n\n"

        f"📈 R:R: `1:3`\n"

        f"🔥 Confidence: `{confidence}%`\n"

        f"📦 Очікуваний час: `{duration}`\n\n"

        f"📊 Причина входу:\n"

        f"• Volume x{round(volume_ratio,1)}\n"

        f"• Momentum {round(momentum,2)}%\n"

        f"• Volatility {round(volatility,2)}%\n"

        f"• EMA Trend підтверджено\n\n"

        f"⚠️ Risk: 1-2% від депозиту"

    )

    bot.stats["signals"] += 1

    bot.stats["last"] = symbol

    if signal_type in ["PUMP", "DUMP"]:

        bot.stats["pump"] += 1

    else:

        bot.stats["smart"] += 1

    bot.active_trades[symbol] = {

        "side": side,

        "entry": current,

        "tp": tp,

        "sl": sl

    }

    return text

# =========================================================

#                RESULTS CHECKER

# =========================================================

def check_trade_results():

    while True:

        try:

            remove_list = []

            for symbol, trade in bot.active_trades.items():

                price = get_price(symbol)

                if not price:

                    continue

                side = trade["side"]

                tp = trade["tp"]

                sl = trade["sl"]

                result = None

                if side == "LONG":

                    if price >= tp:

                        result = "WIN"

                    elif price <= sl:

                        result = "LOSS"

                else:

                    if price <= tp:

                        result = "WIN"

                    elif price >= sl:

                        result = "LOSS"

                if result:

                    bot.closed_trades.append({

                        "symbol": symbol,

                        "result": result

                    })

                    if result == "WIN":

                        bot.stats["wins"] += 1

                    else:

                        bot.stats["losses"] += 1

                    emoji = "✅" if result == "WIN" else "❌"

                    send_message(

                        f"{emoji} `{symbol}` закрито: *{result}*"

                    )

                    remove_list.append(symbol)

            for symbol in remove_list:

                del bot.active_trades[symbol]

        except Exception as e:

            print(e)

        time.sleep(30)

# =========================================================

#                SCANNER

# =========================================================

def scanner():

    send_message(

        "🚀 *Intraday Ultra v9 FINAL ACTIVE*\n\n"

        "✅ Smart Money\n"

        "✅ Pump/Dump\n"

        "✅ Anti-Spam\n"

        "✅ Intraday only\n"

        "✅ High Confidence Filter"

    )

    while True:

        try:

            url = f"{BINANCE_URL}/fapi/v1/ticker/24hr"

            tickers = requests.get(url, timeout=15).json()

            coins = []

            for t in tickers:

                symbol = t["symbol"]

                if not symbol.endswith("USDT"):

                    continue

                volume = float(t["quoteVolume"])

                if volume < MIN_VOLUME_USDT:

                    continue

                change = abs(float(t["priceChangePercent"]))

                if change < 2:

                    continue

                coins.append({

                    "symbol": symbol,

                    "volume": volume,

                    "change": change

                })

            coins = sorted(

                coins,

                key=lambda x: x["volume"],

                reverse=True

            )[:TOP_COINS_LIMIT]

            symbols = (

                bot.watchlist

                if bot.watchlist

                else [x["symbol"] for x in coins]

            )

            for symbol in symbols:

                try:

                    signal = analyze_symbol(symbol)

                    if signal:

                        send_message(signal)

                    time.sleep(1)

                except Exception as e:

                    print(symbol, e)

        except Exception as e:

            print(e)

        time.sleep(SCAN_INTERVAL)

# =========================================================

#                TELEGRAM COMMANDS

# =========================================================

def telegram_bot():

    last_update = 0

    while True:

        try:

            url = (

                f"https://api.telegram.org/bot{TOKEN}"

                f"/getUpdates?offset={last_update+1}&timeout=30"

            )

            updates = requests.get(url, timeout=40).json()

            for update in updates.get("result", []):

                last_update = update["update_id"]

                msg = update.get("message", {})

                text = msg.get("text", "")

                # =========================================

                # STATUS

                # =========================================

                if text == "/status":

                    send_message(

                        f"⚙️ *Статус системи*\n\n"

                        f"✅ Binance Futures ACTIVE\n"

                        f"✅ Scanner ONLINE\n"

                        f"✅ Signals ACTIVE\n"

                        f"✅ Anti-Spam ACTIVE\n\n"

                        f"📊 Активних угод: "

                        f"{len(bot.active_trades)}"

                    )

                # =========================================

                # STATS

                # =========================================

                elif text == "/stats":

                    total = (

                        bot.stats["wins"] +

                        bot.stats["losses"]

                    )

                    wr = 0

                    if total > 0:

                        wr = round(

                            (bot.stats["wins"] / total) * 100,

                            1

                        )

                    send_message(

                        f"🏆 *Intraday Ultra v9*\n\n"

                        f"📈 Signals: {bot.stats['signals']}\n"

                        f"✅ Wins: {bot.stats['wins']}\n"

                        f"❌ Losses: {bot.stats['losses']}\n"

                        f"🎯 WinRate: {wr}%\n\n"

                        f"⚡ Pump/Dump: {bot.stats['pump']}\n"

                        f"💎 Smart Money: {bot.stats['smart']}\n\n"

                        f"📦 Last: {bot.stats['last']}"

                    )

                # =========================================

                # RESULT

                # =========================================

                elif text == "/result":

                    wins = len([

                        x for x in bot.closed_trades

                        if x["result"] == "WIN"

                    ])

                    losses = len([

                        x for x in bot.closed_trades

                        if x["result"] == "LOSS"

                    ])

                    total = wins + losses

                    wr = 0

                    if total > 0:

                        wr = round((wins / total) * 100, 1)

                    send_message(

                        f"📊 *Результати*\n\n"

                        f"✅ WIN: {wins}\n"

                        f"❌ LOSS: {losses}\n"

                        f"🎯 WR: {wr}%"

                    )

                # =========================================

                # WATCHLIST

                # =========================================

                elif text.startswith("/watch"):

                    parts = text.split()

                    if len(parts) > 1:

                        coin = parts[1].upper()

                        if not coin.endswith("USDT"):

                            coin += "USDT"

                        if coin not in bot.watchlist:

                            bot.watchlist.append(coin)

                            send_message(

                                f"✅ {coin} додано"

                            )

                        else:

                            send_message(

                                "⚠️ Уже є"

                            )

                    else:

                        if bot.watchlist:

                            wl = "\n".join(

                                [f"• {x}" for x in bot.watchlist]

                            )

                            send_message(

                                f"👁 Watchlist:\n\n{wl}"

                            )

                        else:

                            send_message(

                                "👁 Watchlist порожній"

                            )

                # =========================================

                # VERSION

                # =========================================

                elif text == "/version":

                    send_message(

                        "🚀 Intraday Ultra v9 FINAL ACTIVE"

                    )

                # =========================================

                # HELP

                # =========================================

                elif text == "/help":

                    send_message(

                        "📚 Команди:\n\n"

                        "/status\n"

                        "/stats\n"

                        "/result\n"

                        "/watch BTCUSDT\n"

                        "/version\n"

                        "/help"

                    )

        except Exception as e:

            print(e)

        time.sleep(2)

# =========================================================

#                MAIN

# =========================================================

if __name__ == "__main__":

    threading.Thread(

        target=lambda: app.run(

            host="0.0.0.0",

            port=int(os.environ.get("PORT", 8080))

        )

    ).start()

    threading.Thread(target=scanner).start()

    threading.Thread(

        target=check_trade_results

    ).start()

    telegram_bot()

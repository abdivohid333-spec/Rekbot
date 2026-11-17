import os
import aiohttp
from aiohttp import web
import telebot
import requests
import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor

# ==========================================
# TOKENLARNI ANIQLASH (Environment Variable yoki o'rnatilgan ro'yxat)
# ==========================================
# Agar Render'da BOT_TOKEN o'rnatilgan bo'lsa, uni oladi, bo'lmasa quyidagi standart 15 ta tokenni ishlatadi
DEFAULT_TOKENS = [
    "9161857693:AAH0FKe_64a0hlBAOEl1XSV3RKio9HcAB2U",
    "9168857205:AAE_y2wmhnRoDc1cdoilYeWsTx1paJXYOOU",
    "9020615009:AAEbV8864UbsaI5S7z09mmaxN9s9yUS71TE",
    "8846195735:AAG31765-y8ZSpfWGB38xPFkwxwNKih0Wvc",
    "8684961175:AAF-EugA4UUMEnOKuNRGxHAg7L5UK-hA9xw",
    "8614193525:AAHmPEuVyLGf9y_1Pk32Bi_7wOthGdoVTF0",
    "8892329293:AAE81rvRwv37Duklrgq80tdo9xULDTZM-3A",
    "8839585037:AAHiLdafW4gdJllq6XYcWVHEiMNOxvXIIDw",
    "8780781642:AAFKuXw5lgJrmJotxdslvV6Y-_F7TKYPrkg",
    "8230491436:AAErxaPtJKHZWi70QCu4jc4P-PY9ZHsUnqU",
    "8730555029:AAHuY0QSrgJ1OX6NSFriiP9otWK_0dyy1zc",
    "8480258106:AAGaYgSgPdHFeO_ZGIZBAQKNV55fMFEYwWc",
    "8748806150:AAEU9zqdoF55Z70Iz8_55IeFRJs495Nstg",
    "8796590031:AAHTHpEOkWLfJHVHCd6MpZHy0q6rHOCSYls",
    "9297134834:AAGkctplyIbFFOI0hD7npFkGmNM3nokznpA",
]

env_token = os.getenv("BOT_TOKEN")
if env_token:
    TOKENS = [t.strip() for t in env_token.split(",") if t.strip()]
else:
    TOKENS = DEFAULT_TOKENS

# ==========================================
# 17 TA EMOJI REAKSIYA
# ==========================================
REACTIONS = [
    "👍", "❤️", "🔥", "🥰", "👏", "😁", "🎉", "💯", "🙏", "👌",
    "🏆", "🕊", "💪", "😱", "🤯", "😵", "👌"
]

RESTART_DELAY = 3
MAX_RESTARTS  = 100

# So'rovlar tez ishlashi uchun umumiy tarmoq executor'i
executor = ThreadPoolExecutor(max_workers=30)

# ==========================================
# WEBHOOK TOZALASH
# ==========================================
def delete_webhook(token):
    try:
        requests.get(
            f"https://api.telegram.org/bot{token}/deleteWebhook?drop_pending_updates=True",
            timeout=5
        )
    except Exception:
        pass

# ==========================================
# REAKSIYA YUBORISH
# ==========================================
def send_reaction_task(token, chat_id, message_id, bot_id):
    emoji = random.choice(REACTIONS)
    url = f"https://api.telegram.org/bot{token}/setMessageReaction"
    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
        "reaction": [{"type": "emoji", "emoji": emoji}],
    }
    
    for _ in range(3):
        try:
            resp = requests.post(url, json=payload, timeout=7)
            if resp.status_code == 200:
                print(f"[{bot_id}] ✅ {emoji}")
                return
            elif resp.status_code == 429:
                retry_after = resp.json().get("parameters", {}).get("retry_after", 2)
                time.sleep(retry_after)
            else:
                break
        except Exception:
            time.sleep(1)

def trigger_reaction(token, chat_id, message_id, bot_id):
    executor.submit(send_reaction_task, token, chat_id, message_id, bot_id)

# ==========================================
# BOT YARATISH
# ==========================================
def make_bot(token):
    bot_id = token.split(":")[0]
    bot = telebot.TeleBot(token, num_threads=2)

    @bot.message_handler(commands=["start"])
    def on_start(message):
        try:
            bot.send_message(message.chat.id, "✅ Reaksiya boti ishlamoqda!")
        except Exception:
            pass

    @bot.channel_post_handler(content_types=[
        "text", "photo", "video", "audio", "document",
        "voice", "video_note", "sticker", "animation",
        "poll", "location", "contact", "venue"
    ])
    def on_post(message):
        trigger_reaction(token, message.chat.id, message.message_id, bot_id)

    @bot.edited_channel_post_handler(content_types=["text", "photo", "video"])
    def on_edited_post(message):
        trigger_reaction(token, message.chat.id, message.message_id, bot_id)

    return bot

# ==========================================
# BOT RUN LOOP
# ==========================================
def run_bot(token):
    bot_id = token.split(":")[0]
    restarts = 0

    while restarts < MAX_RESTARTS:
        delete_webhook(token)
        bot = make_bot(token)

        try:
            print(f"[{bot_id}] 🟢 Ishga tushdi (#{restarts + 1})")
            bot.infinity_polling(
                timeout=30,
                long_polling_timeout=20,
                interval=0,
                allowed_updates=["message", "channel_post", "edited_channel_post"],
            )
        except Exception as e:
            print(f"[{bot_id}] 💥 Xato: {e}")
        finally:
            try:
                bot.stop_polling()
            except Exception:
                pass

        restarts += 1
        if restarts < MAX_RESTARTS:
            print(f"[{bot_id}] 🔄 {RESTART_DELAY}s dan so'ng qayta ulanadi...")
            time.sleep(RESTART_DELAY)

    print(f"[{bot_id}] 🔴 Limit tugadi.")

# ==========================================
# AIOHTTP WEB SERVER (UptimeRobot uchun)
# ==========================================
async def handle_ping(request):
    return web.Response(text="Bot is running and alive!")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle_ping)
    app.router.add_get("/health", handle_ping)
    
    port = int(os.getenv("PORT", 10000))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"🌐 Web server {port}-portda ishga tushdi.")

def run_web_server_in_thread():
    import asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(start_web_server())
    loop.run_forever()

# ==========================================
# MAIN
# ==========================================
if __name__ == "__main__":
    tokens = list(dict.fromkeys([t.strip() for t in TOKENS if t.strip()]))

    # 1. Veb-serverni alohida oqimda ishga tushiramiz (Render portni band qilishi uchun)
    server_thread = threading.Thread(target=run_web_server_in_thread, daemon=True)
    server_thread.start()

    # 2. Har bir botni alohida oqimda ishga tushiramiz
    for token in tokens:
        t = threading.Thread(target=run_bot, args=(token,), daemon=True)
        t.start()
        time.sleep(0.3)

    print(f"🚀 {len(tokens)} ta bot muvaffaqiyatli ishga tushdi!")

    while True:
        time.sleep(60)
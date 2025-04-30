import logging
import json
import uuid
import asyncio
import os
import requests  # type: ignore
import socket
import threading
import base64
import httpx
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.environ.get("BOT_TOKEN")
DATA_FILE = "data.json"
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
GITHUB_REPO = "alinaermish/nfc-redirect-site"
GITHUB_BRANCH = "main"
GITHUB_FILE_PATH = "data.json"
SELF_URL = os.environ.get("RENDER_EXTERNAL_URL")
ADMIN_ID = 302108623

# === GitHub JSON загрузка при старте ===
def restore_data_from_github():
    try:
        url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{GITHUB_FILE_PATH}"
        headers = {
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "Accept": "application/vnd.github+json"
        }
        res = requests.get(url, headers=headers)
        if res.status_code == 200:
            content = res.json().get("content", "")
            decoded = base64.b64decode(content).decode("utf-8")
            with open(DATA_FILE, "w") as f:
                f.write(decoded)
            print("✅ data.json восстановлен из GitHub")
        else:
            print("⚠️ Не удалось получить data.json с GitHub:", res.text)
    except Exception as e:
        print("❌ Ошибка при загрузке data.json из GitHub:", e)

# === Загрузка и сохранение ===
def load_data():
    try:
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)
    push_to_github()

def push_to_github():
    try:
        print("🚀 push_to_github() вызвана")
        with open(DATA_FILE, "rb") as f:
            base64_content = base64.b64encode(f.read()).decode("utf-8")

        url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{GITHUB_FILE_PATH}"
        headers = {
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "Accept": "application/vnd.github+json"
        }

        get_resp = requests.get(url, headers=headers)
        print("📥 Ответ GET от GitHub:", get_resp.status_code, get_resp.text)
        sha = get_resp.json().get("sha") if get_resp.status_code == 200 else None

        payload = {
            "message": "update data.json from bot",
            "content": base64_content,
            "branch": GITHUB_BRANCH
        }
        if sha:
            payload["sha"] = sha

        res = requests.put(url, json=payload, headers=headers)
        print("📤 Ответ PUT от GitHub:", res.status_code, res.text)

        if res.status_code not in [200, 201]:
            print("❌ GitHub API push failed:", res.json())
        else:
            print("✅ data.json обновлён на GitHub")
    except Exception as e:
        print("❌ Ошибка при обновлении GitHub:", e)

def is_valid_link(link):
    return link.startswith("http://") or link.startswith("https://")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    data = load_data()
    data[user_id] = {"step": "waiting_for_link", "pets": []}
    save_data(data)
    await update.message.reply_text("Привет👋🏼\nЭтот бот поможет тебе сделать ссылку для NFC тэга в адресснике✨\n\nПришли ссылку на Taplink или другую, которую ты хочешь, чтобы увидел нашедший👀 \nЭто может быть ссылка с твоими контактами, как taplink, или же просто ссылка на чат с тобой, например https://wa.me/+7XXXXXXXXXX")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    mention = user.mention_html() if user.username else f"ID: {user.id}"
    await context.bot.send_message(chat_id=ADMIN_ID, text=f"🚨 Кто-то вызвал помощь: {mention}", parse_mode="HTML")
    await update.message.reply_text("Спасибо, твой запрос отправлен. Я свяжусь с тобой как можно скорее ✨")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    text = update.message.text.strip()
    data = load_data()

    if user_id not in data:
        data[user_id] = {"step": "waiting_for_link", "pets": []}
        save_data(data)
        await update.message.reply_text("Пришли ссылку на Taplink или другую, которую ты хочешь, чтобы увидел нашедший👀")
        return

    step = data[user_id].get("step")

    if step == "waiting_for_link":
        if is_valid_link(text):
            data[user_id]["current_pet"] = {"link": text}
            data[user_id]["step"] = "confirm_redirect"
            save_data(data)
            await update.message.reply_text(
                "Ты хочешь, чтобы нашедший питомца перешёл по этой ссылке?",
                reply_markup=ReplyKeyboardMarkup([["Да", "Нет"]], one_time_keyboard=True, resize_keyboard=True)
            )
        else:
            await update.message.reply_text("Это не похоже на ссылку. Попробуй ещё раз. \nПопробуй начать с https://")

    elif step == "confirm_redirect":
        if text.lower() == "да":
            data[user_id]["step"] = "ask_recipient"
            save_data(data)
            await update.message.reply_text(
                "Кому отправлять геолокацию питомца, когда его найдут?\nВыбери вариант:",
                reply_markup=ReplyKeyboardMarkup(
                    [["Мне", "Мне и другому человеку", "Другому человеку"]],
                    one_time_keyboard=True, resize_keyboard=True
                )
            )
        elif text.lower() == "нет":
            data[user_id]["step"] = "waiting_for_link"
            save_data(data)
            await update.message.reply_text("Ок, тогда пришли правильную ссылку.")
        else:
            await update.message.reply_text("Выбери 'Да' или 'Нет'.")

    elif step == "ask_recipient":
        if text == "Мне":
            data[user_id]["current_pet"]["owner_ids"] = [user_id]
            data[user_id]["step"] = "ask_pet_name"
            save_data(data)
            await update.message.reply_text("Как зовут твоего питомца?🦄")
        elif text in ["Мне и другому человеку", "Другому человеку"]:
            data[user_id]["step"] = "ask_other_id"
            data[user_id]["current_pet"]["include_self"] = (text == "Мне и другому человеку")
            save_data(data)
            await update.message.reply_text("Пожалуйста, отправь Telegram ID другого человека.\nЕсли не знаешь, как найти ID, напиши @userinfobot и перешли ему любое сообщение от нужного человека и он покажет его ID.\nКак сделаешь, пришли в этот чат ID\n\nНе забудь, чтобы бот смог отправить геолокацию другому человеку, он должен присоединиться к боту (написать в чат бота /start)")
        else:
            await update.message.reply_text("Выбери один из вариантов.")

    elif step == "ask_other_id":
        if text.isdigit():
            other_id = text
            include_self = data[user_id]["current_pet"].get("include_self", False)
            owner_ids = [other_id]
            if include_self:
                owner_ids.append(user_id)
            data[user_id]["current_pet"]["owner_ids"] = owner_ids
            data[user_id]["step"] = "ask_pet_name"
            save_data(data)
            await update.message.reply_text("Как зовут твоего питомца?🦄")
        else:
            await update.message.reply_text("ID должен состоять из цифр🙈")

    elif step == "ask_pet_name":
        data[user_id]["current_pet"]["name"] = text
        pet_uuid = str(uuid.uuid4())
        data[user_id]["current_pet"]["uuid"] = pet_uuid
        data[user_id]["pets"].append(data[user_id]["current_pet"])
        del data[user_id]["current_pet"]
        data[user_id]["step"] = "waiting_for_link"
        save_data(data)

        redirect_url = f"https://findmypetbot.vercel.app/location?uuid={pet_uuid}"
        await update.message.reply_text(f"Готово🎉 \nВот ссылка:\n{redirect_url}")

    else:
        data[user_id]["step"] = "waiting_for_link"
        save_data(data)
        await update.message.reply_text("Начни сначала, пришли ссылку🔗")

# === Самопробуждение и запуск ===
async def ping_self():
    while True:
        try:
            if SELF_URL:
                async with httpx.AsyncClient() as client:
                    await client.get(SELF_URL)
                print("📡 Self-ping successful")
        except Exception as e:
            print("❌ Self-ping failed:", e)
        await asyncio.sleep(300)

def fake_server():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("0.0.0.0", 8080))
        s.listen()
        while True:
            conn, addr = s.accept()
            with conn:
                conn.sendall(b"HTTP/1.1 200 OK\nContent-Type: text/plain\n\nFake port is live.\n")

def start_all():
    restore_data_from_github()
    threading.Thread(target=fake_server, daemon=True).start()
    loop = asyncio.get_event_loop()
    loop.create_task(ping_self())
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    loop.run_until_complete(app.run_polling())

if __name__ == "__main__":
    try:
        asyncio.get_running_loop()
        print("⚠️ Event loop already running")
    except RuntimeError:
        start_all()

import logging
import json
import uuid
import asyncio
import os
import requests # type: ignore
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, MessageHandler, CommandHandler, filters, ContextTypes

# --- ЛОГИ ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- КОНСТАНТЫ ---
TOKEN = os.environ.get("BOT_TOKEN")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
GITHUB_REPO = "alinaermish/nfc-redirect-site"
DATA_FILE = "data.json"

# --- GITHUB PUSH ---
def push_to_github():
    if not GITHUB_TOKEN:
        print("⚠️ GITHUB_TOKEN не установлен")
        return

    api_url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/bot/data.json"

    with open(DATA_FILE, "rb") as f:
        content = f.read()
    encoded_content = content.encode("base64") if hasattr(content, 'encode') else content.decode("utf-8").encode("utf-8").hex()

    # Получаем sha текущего файла
    r = requests.get(api_url, headers={"Authorization": f"token {GITHUB_TOKEN}"})
    sha = r.json().get("sha")

    data = {
        "message": "update data.json from bot",
        "content": content.decode("utf-8").encode("base64") if hasattr(content, 'encode') else content.decode("utf-8").encode("utf-8").hex(),
        "branch": "main"
    }
    if sha:
        data["sha"] = sha

    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }

    r = requests.put(api_url, headers=headers, json=data)
    if r.status_code in [200, 201]:
        print("✅ Успешно отправлено в GitHub")
    else:
        print(f"❌ Ошибка при пуше: {r.status_code}, {r.text}")

# --- ЗАГРУЗКА/СОХРАНЕНИЕ ДАННЫХ ---
def load_data():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)
    push_to_github()

# --- ПРОВЕРКА ССЫЛКИ ---
def is_valid_link(link):
    return link.startswith("http://") or link.startswith("https://")

# --- ХЕНДЛЕРЫ ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    data = load_data()
    data[user_id] = {"step": "waiting_for_link", "pets": []}
    save_data(data)
    await update.message.reply_text("Привет! Пожалуйста, пришли ссылку на Taplink или другую ссылку, которую ты хочешь, чтобы увидел нашедший👀")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    text = update.message.text.strip()
    data = load_data()

    if user_id not in data:
        data[user_id] = {"step": "waiting_for_link", "pets": []}
        save_data(data)
        await update.message.reply_text("Пожалуйста, пришли ссылку на Taplink или другой сайт🙏🏻")
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
            await update.message.reply_text("Это не похоже на ссылку. Попробуй ещё раз.\nПопробуй начать с https://")

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
            await update.message.reply_text("Пожалуйста, выбери 'Да' или 'Нет'.")

    elif step == "ask_recipient":
        if text == "Мне":
            data[user_id]["current_pet"]["owner_ids"] = [user_id]
            data[user_id]["step"] = "ask_pet_name"
            save_data(data)
            await update.message.reply_text("Как зовут питомца?🍀")
        elif text in ["Мне и другому человеку", "Другому человеку"]:
            data[user_id]["step"] = "ask_other_id"
            data[user_id]["current_pet"]["include_self"] = (text == "Мне и другому человеку")
            save_data(data)
            await update.message.reply_text(
                "Пожалуйста, отправь Telegram ID другого человека.\n"
                "Если не знаешь, как найти ID, напиши @userinfobot и перешли ему любое сообщение от нужного человека и он покажет его ID.\n\n"
                "Не забудь, чтобы бот смог отправить геолокацию другому человеку, он должен присоединиться к боту (написать в чат бота /start)"
            )
        else:
            await update.message.reply_text("Пожалуйста, выбери один из предложенных вариантов.")

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
            await update.message.reply_text("Как зовут твоего питомца?✨")
        else:
            await update.message.reply_text("ID должен состоять только из цифр. Попробуй ещё раз.")

    elif step == "ask_pet_name":
        data[user_id]["current_pet"]["name"] = text
        pet_uuid = str(uuid.uuid4())
        data[user_id]["current_pet"]["uuid"] = pet_uuid
        data[user_id]["pets"].append(data[user_id]["current_pet"])
        del data[user_id]["current_pet"]
        data[user_id]["step"] = "waiting_for_link"
        save_data(data)

        redirect_url = f"https://findmypetbot.vercel.app/location?uuid={pet_uuid}"
        await update.message.reply_text(
            f"✅Готово! Вот ссылка для NFC-тега:\n{redirect_url}\n\n"
            "Добавь эту ссылку в тег и прикрепи к ошейнику питомца."
        )

    else:
        data[user_id]["step"] = "waiting_for_link"
        save_data(data)
        await update.message.reply_text("Пожалуйста, следуй шагам. Начни с отправки ссылки.")

# --- ФАЛЬШ-ПОРТ ДЛЯ RENDER ---
class FakeHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is running")

def run_fake_server():
    server_address = ('0.0.0.0', 8080)
    httpd = HTTPServer(server_address, FakeHandler)
    httpd.serve_forever()

threading.Thread(target=run_fake_server, daemon=True).start()

# --- ЗАПУСК ---
def run_bot():
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    return application.run_polling()

try:
    asyncio.get_running_loop()
    print("✅ Bot is already running in existing loop")
except RuntimeError:
    asyncio.run(run_bot())

import logging
import json
import uuid
import asyncio
import os
import requests  # type: ignore
import socket
import threading
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

        with open(DATA_FILE, "r") as f:
            content = f.read()

        url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{GITHUB_FILE_PATH}"
        headers = {
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "Accept": "application/vnd.github+json"
        }

        # Сначала получим SHA
        get_resp = requests.get(url, headers=headers)
        print("📥 Ответ GET от GitHub:", get_resp.status_code, get_resp.text)
        sha = get_resp.json().get("sha") if get_resp.status_code == 200 else None

        # Кодируем контент
        import base64
        base64_content = base64.b64encode(content.encode("utf-8")).decode("utf-8")

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
    await update.message.reply_text("Привет! Пришли ссылку на Taplink или другую, которую увидит нашедший.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    text = update.message.text.strip()
    data = load_data()

    if user_id not in data:
        data[user_id] = {"step": "waiting_for_link", "pets": []}
        save_data(data)
        await update.message.reply_text("Пришли ссылку на Taplink или другой сайт.")
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
            await update.message.reply_text("Это не похоже на ссылку. Начни с https://")

    elif step == "confirm_redirect":
        if text.lower() == "да":
            data[user_id]["step"] = "ask_recipient"
            save_data(data)
            await update.message.reply_text(
                "Кому отправлять геолокацию?\nВыбери вариант:",
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
            await update.message.reply_text("Как зовут питомца?")
        elif text in ["Мне и другому человеку", "Другому человеку"]:
            data[user_id]["step"] = "ask_other_id"
            data[user_id]["current_pet"]["include_self"] = (text == "Мне и другому человеку")
            save_data(data)
            await update.message.reply_text("Отправь Telegram ID другого человека.")
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
            await update.message.reply_text("Как зовут питомца?")
        else:
            await update.message.reply_text("ID должен быть из цифр.")

    elif step == "ask_pet_name":
        data[user_id]["current_pet"]["name"] = text
        pet_uuid = str(uuid.uuid4())
        data[user_id]["current_pet"]["uuid"] = pet_uuid
        data[user_id]["pets"].append(data[user_id]["current_pet"])
        del data[user_id]["current_pet"]
        data[user_id]["step"] = "waiting_for_link"
        save_data(data)

        redirect_url = f"https://findmypetbot.vercel.app/location?uuid={pet_uuid}"
        await update.message.reply_text(f"Готово! Вот ссылка:\n{redirect_url}")

    else:
        data[user_id]["step"] = "waiting_for_link"
        save_data(data)
        await update.message.reply_text("Начни сначала. Пришли ссылку.")

# Запуск Telegram-бота + фальшивый сервер
def main():
    # Фальшивый порт для Render
    def fake_server():
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("0.0.0.0", 8080))
            s.listen()
            while True:
                conn, addr = s.accept()
                with conn:
                    conn.sendall(b"HTTP/1.1 200 OK\nContent-Type: text/plain\n\nFake port is live.\n")

    threading.Thread(target=fake_server, daemon=True).start()

    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()

if __name__ == "__main__":
    main()

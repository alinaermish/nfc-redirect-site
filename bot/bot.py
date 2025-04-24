import logging
import json
import uuid
import os
import requests # type: ignore
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, MessageHandler, CommandHandler, filters, ContextTypes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("BOT_TOKEN")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
REPO = "alinaermish/nfc-redirect-site"
FILE_PATH = "bot/data.json"
DATA_FILE = "bot/data.json"

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
    url = f"https://api.github.com/repos/{REPO}/contents/{FILE_PATH}"

    with open(DATA_FILE, "rb") as f:
        content = f.read()
        encoded_content = content.encode("base64") if hasattr(content, "encode") else content

    sha = get_file_sha(url)
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }

    payload = {
        "message": "update data.json from bot",
        "content": encoded_content.decode("utf-8"),
        "sha": sha
    }

    res = requests.put(url, headers=headers, json=payload)
    if res.status_code >= 400:
        logger.error("❌ Ошибка при пуше в GitHub: %s", res.text)
    else:
        logger.info("✅ Успешно отправлено на GitHub")

def get_file_sha(url):
    res = requests.get(url, headers={
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    })
    if res.status_code == 200:
        return res.json()["sha"]
    return None

def is_valid_link(link):
    return link.startswith("http://") or link.startswith("https://")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    data = load_data()
    data[user_id] = {
        "step": "waiting_for_link",
        "pets": []
    }
    save_data(data)
    await update.message.reply_text("Привет! Пришли ссылку на Taplink или другую, которую увидит нашедший питомца 👀")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    text = update.message.text.strip()
    data = load_data()

    if user_id not in data:
        data[user_id] = {"step": "waiting_for_link", "pets": []}
        save_data(data)
        await update.message.reply_text("Пожалуйста, пришли ссылку на Taplink или другой сайт 🙏🏻")
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
            await update.message.reply_text("Это не похоже на ссылку. Попробуй ещё раз, начиная с https://")

    elif step == "confirm_redirect":
        if text.lower() == "да":
            data[user_id]["step"] = "ask_recipient"
            save_data(data)
            await update.message.reply_text(
                "Кому отправлять геолокацию, когда питомца найдут?",
                reply_markup=ReplyKeyboardMarkup(
                    [["Мне", "Мне и другому человеку", "Другому человеку"]],
                    one_time_keyboard=True, resize_keyboard=True
                )
            )
        elif text.lower() == "нет":
            data[user_id]["step"] = "waiting_for_link"
            save_data(data)
            await update.message.reply_text("Ок, пришли правильную ссылку.")
        else:
            await update.message.reply_text("Пожалуйста, выбери 'Да' или 'Нет'.")

    elif step == "ask_recipient":
        if text == "Мне":
            data[user_id]["current_pet"]["owner_ids"] = [user_id]
            data[user_id]["step"] = "ask_pet_name"
            save_data(data)
            await update.message.reply_text("Как зовут питомца? 🍀")
        elif text in ["Мне и другому человеку", "Другому человеку"]:
            data[user_id]["step"] = "ask_other_id"
            data[user_id]["current_pet"]["include_self"] = (text == "Мне и другому человеку")
            save_data(data)
            await update.message.reply_text(
                "Отправь Telegram ID другого человека.\n"
                "Для получения ID — напиши @userinfobot и перешли сообщение от нужного пользователя.\n"
                "Не забудь: второй человек должен запустить бота (/start)"
            )
        else:
            await update.message.reply_text("Выбери вариант из предложенных.")

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
            await update.message.reply_text("Как зовут питомца? ✨")
        else:
            await update.message.reply_text("ID должен состоять только из цифр.")

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
            f"✅ Готово! Вот ссылка для NFC-тега:\n{redirect_url}\n\n"
            "Добавь её в тег и прикрепи к ошейнику."
        )
    else:
        data[user_id]["step"] = "waiting_for_link"
        save_data(data)
        await update.message.reply_text("Пожалуйста, начни с отправки ссылки.")

if __name__ == "__main__":
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.run_polling()

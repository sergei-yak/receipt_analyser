import os
import uuid
from dotenv import load_dotenv

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from check_spending_agent import process_receipt_image, ask_spending_question


load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
DOWNLOAD_FOLDER = "downloads"

os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Hi! Send me a receipt/check image, and I will save it.\n\n"
        "Then you can ask questions like:\n"
        "- How much did I spend on water?\n"
        "- What was my last purchase?\n"
        "- Show all historical transactions\n"
        "- Show spending by category\n"
        "- Show cumulative spending over time"
    )


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)

    photo = update.message.photo[-1]
    telegram_file = await photo.get_file()

    file_path = os.path.join(
        DOWNLOAD_FOLDER,
        f"{user_id}_{uuid.uuid4()}.jpg"
    )

    await telegram_file.download_to_drive(file_path)

    result = process_receipt_image(
        user_id=user_id,
        image_path=file_path
    )

    await update.message.reply_text(result["answer"])


async def handle_image_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)

    document = update.message.document
    telegram_file = await document.get_file()

    original_name = document.file_name or "receipt_image"
    extension = os.path.splitext(original_name)[1] or ".jpg"

    file_path = os.path.join(
        DOWNLOAD_FOLDER,
        f"{user_id}_{uuid.uuid4()}{extension}"
    )

    await telegram_file.download_to_drive(file_path)

    result = process_receipt_image(
        user_id=user_id,
        image_path=file_path
    )

    await update.message.reply_text(result["answer"])


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    question = update.message.text

    result = ask_spending_question(
        user_id=user_id,
        question=question
    )

    await update.message.reply_text(result["answer"])

    plot_path = result.get("plot_path")

    if plot_path and os.path.exists(plot_path):
        with open(plot_path, "rb") as photo:
            await update.message.reply_photo(photo=photo)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Send a receipt/check image to save it.\n\n"
        "Ask spending questions like:\n"
        "- How much did I spend on groceries?\n"
        "- What was my last purchase?\n\n"
        "Ask for charts like:\n"
        "- Show all historical transactions\n"
        "- Show spending by category\n"
        "- Show spending by merchant\n"
        "- Show cumulative spending over time\n"
        "- Show distribution of transaction amounts"
    )


def main():
    if not TELEGRAM_BOT_TOKEN:
        raise ValueError("Missing TELEGRAM_BOT_TOKEN in .env file")

    telegram_app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    telegram_app.add_handler(CommandHandler("start", start))
    telegram_app.add_handler(CommandHandler("help", help_command))

    telegram_app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    telegram_app.add_handler(MessageHandler(filters.Document.IMAGE, handle_image_document))
    telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    print("Telegram bot is running...")
    telegram_app.run_polling()


if __name__ == "__main__":
    main()
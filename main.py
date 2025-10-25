from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
import os

TOKEN = os.getenv("BOT_TOKEN")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📸 Сгенерировать фото", callback_data="generate")],
        [InlineKeyboardButton("🧍‍♀️ Мои референсы", callback_data="refs")],
        [InlineKeyboardButton("🎨 Стиль / Сезон", callback_data="style")]
    ]
    await update.message.reply_text(
        "👋 Добро пожаловать в Ellen Neiro Studio (ENS)!",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "generate":
        await query.edit_message_text("Отправь промт или фото для генерации (демо-режим 💫)")
    elif query.data == "refs":
        await query.edit_message_text("Здесь можно загрузить 3 фото-референса 🧍‍♀️")
    elif query.data == "style":
        await query.edit_message_text("Выбери стиль / сезон: весна, лето, осень или зима 🎨")

app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(button))

if __name__ == "__main__":
    app.run_polling()

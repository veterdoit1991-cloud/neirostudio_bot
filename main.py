import os, io, json, uuid, logging
from pathlib import Path
from PIL import Image
from dotenv import load_dotenv

from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters
)

# ---------- настройки ----------
logging.basicConfig(level=logging.INFO)
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не установлен в переменных окружения")

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True, parents=True)
USERS_JSON = DATA_DIR / "users.json"

# ---------- "БД" пользователей ----------
def load_db():
    if USERS_JSON.exists():
        try:
            return json.loads(USERS_JSON.read_text(encoding="utf-8"))
        except Exception as e:
            logging.error(f"Ошибка загрузки users.json: {e}")
            return {}
    return {}

def save_db(db):
    try:
        USERS_JSON.write_text(json.dumps(db, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        logging.error(f"Ошибка сохранения users.json: {e}")

DB = load_db()

# ---------- тексты интерфейса ----------
TXT_WELCOME = "👋 Привет! Я ENS — нейро-студия. Выбери действие ниже:"
# (сократил для ясности, остальные тексты оставил как есть)

# ---------- кнопки и утилиты ----------
def main_menu():
    kb = [[InlineKeyboardButton("➕ Загрузить фото", callback_data="upload_refs")],
          [InlineKeyboardButton("📸 Сгенерировать", callback_data="generate")],
          [InlineKeyboardButton("🖼 Мои фото", callback_data="my_refs"),
           InlineKeyboardButton("ℹ️ Помощь", callback_data="help")]]
    return InlineKeyboardMarkup(kb)

def refs_menu():
    kb = [[InlineKeyboardButton("📤 Добавить/обновить", callback_data="upload_refs")],
          [InlineKeyboardButton("👀 Показать текущие", callback_data="show_refs")],
          [InlineKeyboardButton("❌ Удалить все", callback_data="clear_refs")],
          [InlineKeyboardButton("⬅️ Назад", callback_data="back_home")]]
    return InlineKeyboardMarkup(kb)

def ensure_user(uid: int):
    key = str(uid)
    if key not in DB:
        DB[key] = {"refs": [], "awaiting_refs": False}
        save_db(DB)
    return DB[key]

def save_photo_bytes(b: bytes, folder: Path) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    fname = f"{uuid.uuid4().hex}.jpg"
    fpath = folder / fname
    img = Image.open(io.BytesIO(b)).convert("RGB")
    if img.size[0] < 100 or img.size[1] < 100:
        raise ValueError("Фото слишком маленькое")
    img.save(fpath, "JPEG", quality=95)
    return fpath

def build_internal_prompts(user_text: str | None):
    base_prompts = [
        "soft natural smile, warm studio light, fashion portrait, realistic skin, cinematic depth",
        "confident gaze, 3/4 angle, elegant posture, editorial lighting, modern mood",
        "laughing gently, relaxed pose, golden tones, soft contrast, wider frame",
        "serene expression, head turned aside, close-up, smooth light and shadow"
    ]
    return [f"{user_text}, {p}" if user_text else p for p in base_prompts]

def run_generation(ref_images: list[Path], style_image: Path | None, prompts: list[str]) -> list[bytes] | None:
    """Подключи API (Gemini/Replicate) для генерации 4 изображений."""
    return None

# ---------- handlers ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_user(update.effective_user.id)
    if update.message:
        await update.message.reply_text(TXT_WELCOME, reply_markup=main_menu())

async def on_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    u = ensure_user(uid)

    if q.data == "upload_refs":
        u["awaiting_refs"] = True
        save_db(DB)
        await q.edit_message_text(
            "Загрузите 1–3 фото лица. Отправьте их одним или несколькими сообщениями.",
            reply_markup=main_menu()
        )

    elif q.data == "generate":
        if not u["refs"]:
            await q.edit_message_text(TXT_NEED_REFS, reply_markup=main_menu())
        else:
            await q.edit_message_text(TXT_GENERATE_HINT, reply_markup=main_menu())

    elif q.data == "my_refs":
        await q.edit_message_text("Управление фото:", reply_markup=refs_menu())

    elif q.data == "show_refs":
        refs = [Path(p) for p in u["refs"]]
        if not refs:
            await q.edit_message_text("Нет фото. Добавьте через «📤».", reply_markup=refs_menu())
            return
        media = [InputMediaPhoto(open(p, "rb").read(), caption=f"ref {i+1}") for i, p in enumerate(refs[:3])]
        await q.message.reply_media_group(media)
        await q.message.reply_text("Готово ✅", reply_markup=refs_menu())

    elif q.data == "clear_refs":
        for p in u["refs"]:
            try:
                Path(p).unlink(missing_ok=True)
            except Exception as e:
                logging.error(f"Ошибка удаления {p}: {e}")
        u["refs"] = []
        save_db(DB)
        await q.edit_message_text("Фото удалены. Загрузите новые.", reply_markup=main_menu())

    elif q.data == "back_home":
        await q.edit_message_text(TXT_WELCOME, reply_markup=main_menu())

    elif q.data == "help":
        await q.edit_message_text(
            "Как пользоваться: Загрузите 1–3 фото → сгенерируйте через «📸» с рефом/текстом.",
            reply_markup=main_menu()
        )

async def on_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    u = ensure_user(uid)
    photo = update.message.photo[-1]
    file = await context.bot.get_file(photo.file_id)
    b = await file.download_as_bytearray()

    if u.get("awaiting_refs") or len(u["refs"]) < 3:
        user_dir = DATA_DIR / str(uid) / "refs"
        fpath = save_photo_bytes(b, user_dir)
        u["refs"].append(str(fpath))
        u["awaiting_refs"] = len(u["refs"]) < 3
        save_db(DB)
        left = 3 - len(u["refs"])
        await update.message.reply_text(TXT_AFTER_REF_ADDED.format(left=left) if left > 0 else TXT_REFS_DONE)
        return

    style_dir = DATA_DIR / str(uid) / "style_inputs"
    style_path = save_photo_bytes(b, style_dir)
    context.user_data["last_style_image"] = str(style_path)
    await update.message.reply_text("Фото-референс получен. Отправьте текст или /go.")

async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["last_text"] = update.message.text.strip()
    await update.message.reply_text("Текст сохранён. Напишите /go.")

async def cmd_go(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    u = ensure_user(uid)
    if not u["refs"]:
        await update.message.reply_text(TXT_NEED_REFS)
        return

    user_text = context.user_data.get("last_text")
    style_image_path = context.user_data.get("last_style_image")
    prompts = build_internal_prompts(user_text)

    await update.message.reply_text("✨ Генерирую…")
    imgs = run_generation(
        ref_images=[Path(p) for p in u["refs"]],
        style_image=Path(style_image_path) if style_image_path else None,
        prompts=prompts
    )
    if not imgs:
        await update.message.reply_text(TXT_GEN_NOT_CONFIGURED)
        return

    media = [InputMediaPhoto(imgs[0], caption="Кадр 1")]
    for i in range(1, min(4, len(imgs))):
        media.append(InputMediaPhoto(imgs[i], caption=f"Кадр {i+1}"))
    await update.message.reply_media_group(media)
    await update.message.reply_text("Готово ✅")
    context.user_data.clear()  # Очищаем после генерации

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("go", cmd_go))
    app.add_handler(CallbackQueryHandler(on_buttons))
    app.add_handler(MessageHandler(filters.PHOTO, on_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()


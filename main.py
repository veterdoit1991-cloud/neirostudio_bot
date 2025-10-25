import os, io, json, uuid
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

# ---------- базовые настройки ----------
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True, parents=True)
USERS_JSON = DATA_DIR / "users.json"

# ---------- простая "БД" пользователей ----------
def load_db():
    if USERS_JSON.exists():
        try:
            return json.loads(USERS_JSON.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}

def save_db(db):
    USERS_JSON.write_text(json.dumps(db, ensure_ascii=False, indent=2), encoding="utf-8")

DB = load_db()  # структура: { str(user_id): {"refs": [paths], "awaiting_refs": bool} }

# ---------- тексты интерфейса ----------
TXT_WELCOME = (
    "👋 Привет! Я ENS — нейро-студия.\n\n"
    "1) Сначала **загрузи 1–3 своих фото** (крупный план, хороший свет, разные ракурсы). "
    "Я запомню твои черты.\n"
    "2) Затем в разделе **«📸 Сгенерировать»** пришли **фото-референс** (поза/свет) "
    "и/или **короткий текст** — я сделаю **серию из 4 кадров**.\n\n"
    "Выбери действие ниже:"
)

TXT_NEED_REFS = (
    "Сначала загрузите **минимум 1 фото** вашего лица (лучше 2–3 разных ракурса). "
    "Нажмите **«➕ Загрузить фото»** и отправьте снимки."
)

TXT_AFTER_REF_ADDED = (
    "Готово! Фото добавлено.\n"
    "Вы можете загрузить ещё {left} шт. (до 3). "
    "Когда будете готовы — нажмите **«📸 Сгенерировать»**."
)

TXT_REFS_DONE = (
    "Отлично! 3 фото сохранены ✅\n"
    "Теперь нажмите **«📸 Сгенерировать»** и пришлите фото-референс и/или текст.\n"
    "Я создам **4 кадра** с разными эмоциями и ракурсами."
)

TXT_GENERATE_HINT = (
    "Отправьте **фото-референс** (поза/свет) и/или **текст**.\n\n"
    "Можно только фото — я сама сформирую скрытый промт и сделаю **4 кадра**:\n"
    "1) мягкая улыбка, средний план\n"
    "2) дерзкий взгляд, 3/4 ракурс\n"
    "3) смех, более широкий кадр\n"
    "4) нежный профиль, крупный план"
)

TXT_GEN_NOT_CONFIGURED = (
    "🔧 Модуль генерации пока не настроен. Интерфейс работает.\n"
    "Подключи API в функции `run_generation()` в main.py."
)

# ---------- кнопки ----------
def main_menu():
    kb = [
        [InlineKeyboardButton("➕ Загрузить фото", callback_data="upload_refs")],
        [InlineKeyboardButton("📸 Сгенерировать", callback_data="generate")],
        [InlineKeyboardButton("🖼 Мои фото", callback_data="my_refs"),
         InlineKeyboardButton("ℹ️ Помощь", callback_data="help")]
    ]
    return InlineKeyboardMarkup(kb)

def refs_menu():
    kb = [
        [InlineKeyboardButton("📤 Добавить/обновить", callback_data="upload_refs")],
        [InlineKeyboardButton("👀 Показать текущие", callback_data="show_refs")],
        [InlineKeyboardButton("❌ Удалить все", callback_data="clear_refs")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="back_home")]
    ]
    return InlineKeyboardMarkup(kb)

# ---------- утилиты ----------
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
    Image.open(io.BytesIO(b)).convert("RGB").save(fpath, "JPEG", quality=95)
    return fpath

# ---------- скрытый промт-пул (4 вариации) ----------
def build_internal_prompts(user_text: str | None):
    base_prompts = [
        "soft natural smile, warm studio light, fashion portrait, realistic skin, cinematic depth",
        "confident gaze, 3/4 angle, elegant posture, editorial lighting, modern mood",
        "laughing gently, relaxed pose, golden tones, soft contrast, wider frame",
        "serene expression, head turned aside, close-up, smooth light and shadow"
    ]
    if user_text:
        return [f"{user_text}, {p}" for p in base_prompts]
    return base_prompts

# ---------- заглушка генерации (сюда подключишь API) ----------
def run_generation(ref_images: list[Path], style_image: Path | None, prompts: list[str]) -> list[bytes] | None:
    """
    Подключи сюда свой провайдер (Seedream / Replicate / и т.д.).
    Верни список из 4 картинок (bytes).
    Сейчас — заглушка: возвращает None, чтобы бот честно сообщил, что генерация не настроена.
    """
    return None

# ================== HANDLERS ==================

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
            "Загрузите **1–3 фото** вашего лица (лучше разные ракурсы). "
            "Отправляйте их одним или несколькими сообщениями. Когда хватит — перейдите в «📸 Сгенерировать».",
            reply_markup=main_menu()
        )

    elif q.data == "generate":
        if len(u["refs"]) == 0:
            await q.edit_message_text(TXT_NEED_REFS, reply_markup=main_menu())
        else:
            await q.edit_message_text(TXT_GENERATE_HINT, reply_markup=main_menu())

    elif q.data == "my_refs":
        await q.edit_message_text("Управление вашими фото-референсами:", reply_markup=refs_menu())

    elif q.data == "show_refs":
        refs = [Path(p) for p in u["refs"]]
        if not refs:
            await q.edit_message_text("Ещё нет сохранённых фото. Нажмите «📤 Добавить/обновить».", reply_markup=refs_menu())
            return
        media = []
        for i, p in enumerate(refs[:10]):
            with open(p, "rb") as f:
                img = f.read()
            media.append(InputMediaPhoto(img, caption=f"ref {i+1}"))
        await q.message.reply_media_group(media)
        await q.message.reply_text("Готово ✅", reply_markup=refs_menu())

    elif q.data == "clear_refs":
        for p in list(u["refs"]):
            try:
                Path(p).unlink(missing_ok=True)
            except Exception:
                pass
        u["refs"] = []
        save_db(DB)
        await q.edit_message_text("Все референсы удалены. Загрузите новые 1–3 фото.", reply_markup=main_menu())

    elif q.data == "back_home":
        await q.edit_message_text(TXT_WELCOME, reply_markup=main_menu())

    elif q.data == "help":
        await q.edit_message_text(
            "Как пользоваться:\n"
            "• Загрузите 1–3 фото лица (крупно, без фильтров).\n"
            "• В «📸 Сгенерировать» пришлите фото-референс и/или текст — я создам серию из 4 кадров.\n"
            "• «🖼 Мои фото» — посмотреть/обновить/удалить рефы.\n\n"
            "Примечание: модуль генерации подключается в `run_generation()`.",
            reply_markup=main_menu()
        )

async def on_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    u = ensure_user(uid)

    # качаем максимальный размер фото
    photo = update.message.photo[-1]
    file = await context.bot.get_file(photo.file_id)
    b = await file.download_as_bytearray()

    # если ждём референсы — сохраняем до 3 шт.
    if u.get("awaiting_refs", False) or len(u["refs"]) < 3:
        user_dir = DATA_DIR / str(uid) / "refs"
        fpath = save_photo_bytes(b, user_dir)
        u.setdefault("refs", []).append(str(fpath))
        u["awaiting_refs"] = len(u["refs"]) < 3  # продолжаем ждать, пока <3
        save_db(DB)
        left = 3 - len(u["refs"])
        if left > 0:
            await update.message.reply_text(TXT_AFTER_REF_ADDED.format(left=left))
        else:
            await update.message.reply_text(TXT_REFS_DONE)
        return

    # иначе — считаем это style-image для генерации
    style_dir = DATA_DIR / str(uid) / "style_inputs"
    style_path = save_photo_bytes(b, style_dir)
    context.user_data["last_style_image"] = str(style_path)
    await update.message.reply_text("Фото-референс получен. Теперь (при желании) отправьте текст — или сразу напишите «/go» чтобы сгенерировать серию из 4 кадров.")

async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # сохраняем последний текст как потенциальный промт
    context.user_data["last_text"] = update.message.text.strip()
    await update.message.reply_text("Текст получен. Напишите «/go», чтобы сгенерировать 4 кадра.")

async def cmd_go(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    u = ensure_user(uid)
    if len(u["refs"]) == 0:
        await update.message.reply_text(TXT_NEED_REFS)
        return

    user_text = context.user_data.get("last_text")
    style_image_path = context.user_data.get("last_style_image")
    prompts = build_internal_prompts(user_text)

    await update.message.reply_text("✨ Делаю серию из 4 кадров…")

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

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start(update, context)

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("go", cmd_go))  # запускает генерацию по последним данным
    app.add_handler(CallbackQueryHandler(on_buttons))
    app.add_handler(MessageHandler(filters.PHOTO, on_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()


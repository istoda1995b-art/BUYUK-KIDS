import logging
import sqlite3
import random
import io
import qrcode
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes, ConversationHandler
)
import barcode
from barcode.writer import ImageWriter

# ═══════════════════════════════════════════
# SOZLAMALAR
# ═══════════════════════════════════════════
BOT_TOKEN = "7630245766:AAHpChw-kpNDivtXoZk-MTa0cEbc-xj7fjU"
ADMIN_ID = 286262755
WELCOME_BONUS = 100                      # Ro'yxatdan o'tganda beriladigan bonus (ball)
CASHBACK_PERCENT = 4                     # Xariddan keshbek foizi
BOT_USERNAME = "savdo_bot"

# ═══════════════════════════════════════════
# HOLATLAR
# ═══════════════════════════════════════════
WAITING_PHONE = 1
WAITING_CARD = 2
ADMIN_ADD_BONUS = 3
ADMIN_REMOVE_BONUS = 4
CASHIER_SCAN = 5
CASHIER_AMOUNT = 6

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════
# MA'LUMOTLAR BAZASI
# ═══════════════════════════════════════════
def init_db():
    conn = sqlite3.connect("bonus.db")
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            full_name TEXT,
            phone TEXT UNIQUE,
            bonus INTEGER DEFAULT 0,
            registered_at TEXT,
            card_number TEXT UNIQUE
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount INTEGER,
            description TEXT,
            created_at TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS cashiers (
            cashier_id INTEGER PRIMARY KEY,
            name TEXT,
            added_at TEXT
        )
    """)
    conn.commit()
    conn.close()

def get_user(user_id):
    conn = sqlite3.connect("bonus.db")
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = c.fetchone()
    conn.close()
    return user

def get_user_by_phone(phone):
    conn = sqlite3.connect("bonus.db")
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE phone = ?", (phone,))
    user = c.fetchone()
    conn.close()
    return user

def register_user(user_id, username, full_name, phone, card_number):
    conn = sqlite3.connect("bonus.db")
    c = conn.cursor()
    try:
        c.execute("""
            INSERT INTO users (user_id, username, full_name, phone, bonus, registered_at, card_number)
            VALUES (?, ?, ?, ?, 0, ?, ?)
        """, (user_id, username, full_name, phone,
              datetime.now().strftime("%Y-%m-%d %H:%M"), card_number))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def update_bonus(user_id, amount, description):
    conn = sqlite3.connect("bonus.db")
    c = conn.cursor()
    c.execute("UPDATE users SET bonus = bonus + ? WHERE user_id = ?", (amount, user_id))
    c.execute("""
        INSERT INTO transactions (user_id, amount, description, created_at)
        VALUES (?, ?, ?, ?)
    """, (user_id, amount, description, datetime.now().strftime("%Y-%m-%d %H:%M")))
    conn.commit()
    conn.close()

def get_transactions(user_id, limit=5):
    conn = sqlite3.connect("bonus.db")
    c = conn.cursor()
    c.execute("""
        SELECT amount, description, created_at FROM transactions
        WHERE user_id = ? ORDER BY id DESC LIMIT ?
    """, (user_id, limit))
    rows = c.fetchall()
    conn.close()
    return rows

def get_all_users():
    conn = sqlite3.connect("bonus.db")
    c = conn.cursor()
    c.execute("SELECT user_id, full_name, phone, bonus FROM users ORDER BY bonus DESC")
    rows = c.fetchall()
    conn.close()
    return rows

def is_cashier(user_id):
    if user_id == ADMIN_ID:
        return True
    conn = sqlite3.connect("bonus.db")
    c = conn.cursor()
    c.execute("SELECT 1 FROM cashiers WHERE cashier_id = ?", (user_id,))
    result = c.fetchone()
    conn.close()
    return result is not None

def add_cashier(cashier_id, name):
    conn = sqlite3.connect("bonus.db")
    c = conn.cursor()
    try:
        c.execute("INSERT OR REPLACE INTO cashiers (cashier_id, name, added_at) VALUES (?, ?, ?)",
                  (cashier_id, name, datetime.now().strftime("%Y-%m-%d %H:%M")))
        conn.commit()
        return True
    except Exception:
        return False
    finally:
        conn.close()

# ═══════════════════════════════════════════
# KOD GENERATSIYA
# ═══════════════════════════════════════════
def generate_qr_image(user_id: int) -> io.BytesIO:
    data = f"https://t.me/{BOT_USERNAME}?start=pay_{user_id}"
    qr = qrcode.QRCode(version=2, box_size=10, border=4,
                       error_correction=qrcode.constants.ERROR_CORRECT_M)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf

def generate_barcode_image(card_number: str) -> io.BytesIO:
    buf = io.BytesIO()
    EAN13 = barcode.get_barcode_class("ean13")
    ean = EAN13(card_number, writer=ImageWriter())
    ean.write(buf, options={"module_height": 15, "font_size": 10, "text_distance": 5})
    buf.seek(0)
    return buf

# ═══════════════════════════════════════════
# MENYULAR
# ═══════════════════════════════════════════
def main_menu_keyboard(is_registered):
    if is_registered:
        keyboard = [
            [InlineKeyboardButton("🎁 Bonus ballarim", callback_data="my_bonus")],
            [InlineKeyboardButton("📋 Tarix", callback_data="history")],
            [InlineKeyboardButton("💳 Kartam & QR kod", callback_data="my_card")],
        ]
    else:
        keyboard = [
            [InlineKeyboardButton("📝 Ro'yxatdan o'tish", callback_data="register")],
        ]
    return InlineKeyboardMarkup(keyboard)

def admin_keyboard():
    keyboard = [
        [InlineKeyboardButton("➕ Bonus qo'shish", callback_data="admin_add")],
        [InlineKeyboardButton("➖ Bonus ayirish", callback_data="admin_remove")],
        [InlineKeyboardButton("👥 Foydalanuvchilar", callback_data="admin_users")],
        [InlineKeyboardButton("👨‍💼 Kassir qo'shish", callback_data="admin_add_cashier")],
    ]
    return InlineKeyboardMarkup(keyboard)

def cashier_keyboard():
    keyboard = [
        [InlineKeyboardButton("💳 Xarid — keshbek berish", callback_data="cashier_sale")],
    ]
    return InlineKeyboardMarkup(keyboard)

# ═══════════════════════════════════════════
# HANDLERLAR
# ═══════════════════════════════════════════
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    args = context.args

    # Kassir QR skanerlagan: /start pay_12345678
    if args and args[0].startswith("pay_"):
        if not is_cashier(user.id):
            await update.message.reply_text("❌ Siz kassir emassiz.")
            return ConversationHandler.END
        try:
            target_id = int(args[0].replace("pay_", ""))
        except ValueError:
            await update.message.reply_text("❌ Noto'g'ri QR kod.")
            return ConversationHandler.END
        target_user = get_user(target_id)
        if not target_user:
            await update.message.reply_text("❌ Foydalanuvchi topilmadi.")
            return ConversationHandler.END
        context.user_data["cashier_target_id"] = target_id
        await update.message.reply_text(
            f"👤 *{target_user[2]}*\n"
            f"📞 {target_user[3]}\n"
            f"🎁 Joriy bonus: *{target_user[4]} ball*\n\n"
            f"💵 Xarid summasini kiriting (so'm):",
            parse_mode="Markdown"
        )
        return CASHIER_AMOUNT

    db_user = get_user(user.id)
    welcome = f"👋 Salom, *{user.first_name}*!\n\n"
    if db_user:
        welcome += (f"✅ Siz ro'yxatdasiz.\n"
                    f"🎁 Bonus: *{db_user[4]} ball*\n\n"
                    f"📲 Xarid qilganda QR kodingizni kassirga ko'rsating\n"
                    f"va har xariddan *{CASHBACK_PERCENT}%* keshbek oling!")
    else:
        welcome += (f"🛍 Bonus dasturimizga xush kelibsiz!\n"
                    f"Ro'yxatdan o'ting va\n"
                    f"har xariddan *{CASHBACK_PERCENT}%* keshbek to'plang!")

    await update.message.reply_text(
        welcome,
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard(db_user is not None)
    )
    return ConversationHandler.END

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Ruxsat yo'q.")
        return
    await update.message.reply_text("🔧 *Admin panel*", parse_mode="Markdown", reply_markup=admin_keyboard())

async def cashier_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_cashier(update.effective_user.id):
        await update.message.reply_text("❌ Ruxsat yo'q.")
        return
    await update.message.reply_text(
        "👨‍💼 *Kassir paneli*\n\nFoydalanuvchi QR kodini skaner qiling yoki ID kiriting:",
        parse_mode="Markdown",
        reply_markup=cashier_keyboard()
    )

async def my_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    await update.message.reply_text(
        f"🆔 Sizning Telegram ID ingiz:\n`{uid}`\n\n"
        f"_Kassirga bu raqamni bering._",
        parse_mode="Markdown"
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    # ── FOYDALANUVCHI ──────────────────────
    if data == "my_bonus":
        db_user = get_user(user_id)
        if db_user:
            await query.edit_message_text(
                f"🎁 *Bonus ballaringiz*\n\n"
                f"💰 Jami: *{db_user[4]} ball*\n"
                f"📞 Telefon: {db_user[3]}\n\n"
                f"_1 ball ≈ 1 so'm_",
                parse_mode="Markdown",
                reply_markup=main_menu_keyboard(True)
            )

    elif data == "history":
        txns = get_transactions(user_id)
        if txns:
            text = "📋 *So'nggi amallar:*\n\n"
            for amount, desc, date in txns:
                sign = "➕" if amount > 0 else "➖"
                text += f"{sign} *{abs(amount)} ball* — {desc}\n🕐 {date}\n\n"
        else:
            text = "📋 Hali amal yo'q."
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=main_menu_keyboard(True))

    elif data == "my_card":
        db_user = get_user(user_id)
        if db_user:
            card_number = db_user[6] if db_user[6] else None
            await query.edit_message_text(
                f"💳 *Sizning bonus kartangiz*\n\n"
                f"👤 {db_user[2]}\n"
                f"📞 {db_user[3]}\n"
                f"🎁 Bonus: *{db_user[4]} ball*\n"
                f"📅 {db_user[5]}\n\n"
                f"🔢 Karta: `{card_number or '—'}`\n\n"
                f"📲 *QR kod va shtrix-kod* pastda yuboriladi.\nKassirga ko'rsating!",
                parse_mode="Markdown",
                reply_markup=main_menu_keyboard(True)
            )
            # QR kod
            try:
                qr_img = generate_qr_image(user_id)
                await context.bot.send_photo(
                    chat_id=user_id,
                    photo=qr_img,
                    caption=f"📲 *QR kod* — kassirga ko'rsating\n🎁 Har xariddan *{CASHBACK_PERCENT}%* keshbek!",
                    parse_mode="Markdown"
                )
            except Exception as e:
                logger.error(f"QR error: {e}")
            # Shtrix-kod
            if card_number:
                try:
                    barcode_img = generate_barcode_image(card_number)
                    await context.bot.send_photo(
                        chat_id=user_id,
                        photo=barcode_img,
                        caption=f"🔲 Shtrix-kod: `{card_number}`",
                        parse_mode="Markdown"
                    )
                except Exception as e:
                    logger.error(f"Barcode error: {e}")

    elif data == "register":
        await query.edit_message_text(
            "📞 Telefon raqamingizni kiriting:\n_(masalan: +998901234567)_",
            parse_mode="Markdown"
        )
        return WAITING_PHONE

    # ── KASSIR ─────────────────────────────
    elif data == "cashier_sale":
        if not is_cashier(user_id):
            return
        await query.edit_message_text(
            "🔍 Foydalanuvchi Telegram ID sini kiriting:\n_(Foydalanuvchi /myid buyrug'ini yozsa ID ko'rinadi)_",
            parse_mode="Markdown"
        )
        return CASHIER_SCAN

    # ── ADMIN ──────────────────────────────
    elif data == "admin_add":
        if user_id != ADMIN_ID:
            return
        context.user_data["admin_action"] = "add"
        await query.edit_message_text(
            "➕ Telefon raqam va bonus miqdorini kiriting:\n_(masalan: +998901234567 100)_",
            parse_mode="Markdown"
        )
        return ADMIN_ADD_BONUS

    elif data == "admin_remove":
        if user_id != ADMIN_ID:
            return
        context.user_data["admin_action"] = "remove"
        await query.edit_message_text(
            "➖ Telefon raqam va ayiriladigan bonus:\n_(masalan: +998901234567 50)_",
            parse_mode="Markdown"
        )
        return ADMIN_REMOVE_BONUS

    elif data == "admin_users":
        if user_id != ADMIN_ID:
            return
        users = get_all_users()
        if users:
            text = "👥 *Foydalanuvchilar (bonus bo'yicha):*\n\n"
            for i, (uid, name, phone, bonus) in enumerate(users[:20], 1):
                text += f"{i}. {name} | {phone} | 🎁 {bonus} ball\n"
        else:
            text = "Hali foydalanuvchi yo'q."
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=admin_keyboard())

    elif data == "admin_add_cashier":
        if user_id != ADMIN_ID:
            return
        context.user_data["admin_action"] = "add_cashier"
        await query.edit_message_text(
            "👨‍💼 Kassir Telegram ID va ismini kiriting:\n_(masalan: 123456789 Alisher)_",
            parse_mode="Markdown"
        )
        return ADMIN_ADD_BONUS

# ── Ro'yxatdan o'tish ──────────────────────
async def handle_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phone = update.message.text.strip()
    if not phone.startswith("+") or len(phone) < 10:
        await update.message.reply_text("❌ Noto'g'ri format. Qayta kiriting (+998XXXXXXXXX):")
        return WAITING_PHONE
    if get_user_by_phone(phone):
        await update.message.reply_text("⚠️ Bu raqam allaqachon ro'yxatda.")
        return ConversationHandler.END
    context.user_data["phone"] = phone
    await update.message.reply_text(
        "💳 Karta raqamingizni kiriting:\n_(13 ta raqam, masalan: 1234567890123)_",
        parse_mode="Markdown"
    )
    return WAITING_CARD

async def handle_card(update: Update, context: ContextTypes.DEFAULT_TYPE):
    card = update.message.text.strip()
    user = update.effective_user
    if not card.isdigit() or len(card) != 13:
        await update.message.reply_text("❌ Karta raqami 13 ta raqam bo'lishi kerak. Qayta kiriting:")
        return WAITING_CARD
    phone = context.user_data.get("phone")
    success = register_user(user.id, user.username or "", user.full_name, phone, card)
    if success:
        await update.message.reply_text(
            f"✅ *Muvaffaqiyatli ro'yxatdan o'tdingiz!*\n\n"
            f"💳 Karta: `{card}`\n\n"
            f"📲 Har xaridda QR kodingizni kassirga ko'rsating\n"
            f"va *{CASHBACK_PERCENT}%* keshbek to'plang!",
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard(True)
        )
        try:
            qr_img = generate_qr_image(user.id)
            await update.message.reply_photo(
                photo=qr_img,
                caption=f"📲 *Sizning QR kodingiz*\nKassirga ko'rsating — *{CASHBACK_PERCENT}%* keshbek!",
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"QR error: {e}")
        try:
            barcode_img = generate_barcode_image(card)
            await update.message.reply_photo(
                photo=barcode_img,
                caption=f"🔲 Shtrix-kodingiz: `{card}`",
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Barcode error: {e}")
    else:
        await update.message.reply_text("❌ Bu karta raqami allaqachon ro'yxatda yoki xatolik yuz berdi.")
    return ConversationHandler.END

# ── Kassir: ID kiriting ────────────────────
async def handle_cashier_scan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_cashier(update.effective_user.id):
        return ConversationHandler.END
    text = update.message.text.strip()
    try:
        target_id = int(text)
    except ValueError:
        await update.message.reply_text("❌ Faqat raqam kiriting (Telegram ID):")
        return CASHIER_SCAN
    target_user = get_user(target_id)
    if not target_user:
        await update.message.reply_text("❌ Bu ID ga ega foydalanuvchi topilmadi.")
        return CASHIER_SCAN
    context.user_data["cashier_target_id"] = target_id
    await update.message.reply_text(
        f"👤 *{target_user[2]}*\n"
        f"📞 {target_user[3]}\n"
        f"🎁 Joriy bonus: *{target_user[4]} ball*\n\n"
        f"💵 Xarid summasini kiriting (so'm):",
        parse_mode="Markdown"
    )
    return CASHIER_AMOUNT

# ── Kassir: summa kiriting ─────────────────
async def handle_cashier_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_cashier(update.effective_user.id):
        return ConversationHandler.END
    text = update.message.text.strip().replace(" ", "").replace(",", "")
    try:
        amount = int(text)
    except ValueError:
        await update.message.reply_text("❌ Faqat raqam kiriting (summa so'mda):")
        return CASHIER_AMOUNT

    target_id = context.user_data.get("cashier_target_id")
    if not target_id:
        await update.message.reply_text("❌ Xatolik. Qaytadan boshlang.")
        return ConversationHandler.END

    cashback = int(amount * CASHBACK_PERCENT / 100)
    update_bonus(target_id, cashback, f"🛍 Xarid {amount:,} so'm — {CASHBACK_PERCENT}% keshbek")
    target_user = get_user(target_id)
    new_balance = target_user[4]

    await update.message.reply_text(
        f"✅ *Keshbek berildi!*\n\n"
        f"👤 {target_user[2]}\n"
        f"💵 Xarid: *{amount:,} so'm*\n"
        f"🎁 Keshbek: *+{cashback} ball* ({CASHBACK_PERCENT}%)\n"
        f"📊 Yangi balans: *{new_balance} ball*",
        parse_mode="Markdown",
        reply_markup=cashier_keyboard()
    )
    try:
        await context.bot.send_message(
            target_id,
            f"🛍 *Xaridingiz uchun keshbek!*\n\n"
            f"💵 Xarid summasi: *{amount:,} so'm*\n"
            f"🎁 Keshbek: *+{cashback} ball* ({CASHBACK_PERCENT}%)\n"
            f"📊 Jami bonus: *{new_balance} ball*",
            parse_mode="Markdown"
        )
    except Exception:
        pass
    return ConversationHandler.END

# ── Admin bonus/kassir ─────────────────────
async def handle_admin_bonus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return ConversationHandler.END
    action = context.user_data.get("admin_action", "add")

    if action == "add_cashier":
        parts = update.message.text.strip().split(maxsplit=1)
        if len(parts) != 2:
            await update.message.reply_text("❌ Format: 123456789 Alisher")
            return ConversationHandler.END
        try:
            cashier_id = int(parts[0])
            cashier_name = parts[1]
        except ValueError:
            await update.message.reply_text("❌ ID raqam bo'lishi kerak.")
            return ConversationHandler.END
        add_cashier(cashier_id, cashier_name)
        await update.message.reply_text(
            f"✅ Kassir qo'shildi: *{cashier_name}* (`{cashier_id}`)",
            parse_mode="Markdown",
            reply_markup=admin_keyboard()
        )
        return ConversationHandler.END

    parts = update.message.text.strip().split()
    if len(parts) != 2:
        await update.message.reply_text("❌ Format: +998XXXXXXXXX 100")
        return ConversationHandler.END
    phone, amount_str = parts
    try:
        amount = int(amount_str)
    except ValueError:
        await update.message.reply_text("❌ Miqdor raqam bo'lishi kerak.")
        return ConversationHandler.END
    db_user = get_user_by_phone(phone)
    if not db_user:
        await update.message.reply_text("❌ Foydalanuvchi topilmadi.")
        return ConversationHandler.END
    if action == "remove":
        amount = -amount
        desc = "Admin tomonidan ayirildi"
    else:
        desc = "Admin tomonidan qo'shildi"
    update_bonus(db_user[0], amount, desc)
    new_balance = get_user(db_user[0])[4]
    try:
        sign = "➕" if amount > 0 else "➖"
        await context.bot.send_message(
            db_user[0],
            f"{sign} *{abs(amount)} ball* hisobingizga {'qo\'shildi' if amount > 0 else 'ayirildi'}!\n"
            f"📊 Yangi balans: *{new_balance} ball*",
            parse_mode="Markdown"
        )
    except Exception:
        pass
    await update.message.reply_text(
        f"✅ {db_user[2]} ({phone})\nBonus: {'+' if amount > 0 else ''}{amount} ball | Balans: {new_balance} ball",
        reply_markup=admin_keyboard()
    )
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Bekor qilindi.")
    return ConversationHandler.END

# ═══════════════════════════════════════════
# ISHGA TUSHIRISH
# ═══════════════════════════════════════════
def main():
    init_db()
    app = Application.builder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            CallbackQueryHandler(button_handler),
        ],
        states={
            WAITING_PHONE:     [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_phone)],
            WAITING_CARD:      [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_card)],
            CASHIER_SCAN:      [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_cashier_scan)],
            CASHIER_AMOUNT:    [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_cashier_amount)],
            ADMIN_ADD_BONUS:   [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_bonus)],
            ADMIN_REMOVE_BONUS:[MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_bonus)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
    )

    app.add_handler(conv_handler)
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CommandHandler("kassir", cashier_panel))
    app.add_handler(CommandHandler("myid", my_id))

    print("🤖 Bot ishga tushdi...")
    app.run_polling()

if __name__ == "__main__":
    main()

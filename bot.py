#!/usr/bin/env python3
"""
Chakana savdo Telegram boti — to'liq versiya
Rollar: admin | worker (mahsulot qo'shish) | user (xarid)
"""

import logging
import os
import random
import string
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardRemove
)
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
import asyncio
from database import Database

# ========================
# SOZLAMALAR
# ========================
BOT_TOKEN = os.getenv("BOT_TOKEN", "8666809596:AAHfq9JtHvOyS-Qee4B2R_oAuk470r4Y2fY")
ADMIN_IDS = [286262755]
DB_PATH = "shop.db"

SIZES = ["XS", "S", "M", "L", "XL", "XXL", "3XL"]

# Chegirma sozlamalari
DISCOUNT_TIER1_LIMIT = 500_000   # 500,000 so'mgacha
DISCOUNT_TIER1_PCT   = 5         # 5%
DISCOUNT_TIER2_PCT   = 10        # 10%

# ========================
# LOGGING
# ========================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ========================
# BOT VA DISPATCHER
# ========================
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
db = Database(DB_PATH)

# ========================
# HOLATLAR (FSM)
# ========================
class OrderStates(StatesGroup):
    choosing_category = State()
    choosing_product = State()
    choosing_size = State()
    in_cart = State()
    entering_name = State()
    entering_phone = State()
    entering_address = State()
    choosing_payment = State()

class WorkerLoginStates(StatesGroup):
    entering_password = State()

class AdminStates(StatesGroup):
    # Kategoriya
    adding_category_name = State()
    adding_category_sizes = State()
    # Mahsulot qo'shish
    choosing_category_for_product = State()
    adding_product_name = State()
    adding_product_price = State()
    adding_product_description = State()
    adding_product_sizes = State()       # YANGI: razmerlar kiritish
    adding_product_photo = State()
    # Mahsulot tahrirlash
    editing_product_select = State()
    editing_product_field = State()
    editing_product_value = State()
    editing_product_photo_new = State()
    # O'chirish
    deleting_product = State()
    deleting_category = State()
    # Ishchi parol
    creating_worker_password = State()
    # Ishchilarni ko'rish/o'chirish
    removing_worker = State()

# ========================
# YORDAMCHI FUNKSIYALAR
# ========================
def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

def is_worker(user_id: int) -> bool:
    return db.get_user_role(user_id) in ('worker', 'admin') or is_admin(user_id)

def calc_discount(total: int):
    """(chegirma_summasi, yakuniy_narx, foiz) qaytaradi"""
    if total <= 0:
        return 0, total, 0
    pct = DISCOUNT_TIER2_PCT if total >= DISCOUNT_TIER1_LIMIT else DISCOUNT_TIER1_PCT
    discount = int(total * pct / 100)
    return discount, total - discount, pct

def discount_hint(total: int) -> str:
    if total < DISCOUNT_TIER1_LIMIT:
        remaining = DISCOUNT_TIER1_LIMIT - total
        return (
            f"\n\n💡 Yana <b>{remaining:,} so'm</b> xarid qilsangiz, "
            f"chegirma <b>{DISCOUNT_TIER2_PCT}%</b> ga ko'tariladi!"
        )
    return ""

def gen_password(length=8) -> str:
    chars = string.ascii_uppercase + string.digits
    return ''.join(random.choices(chars, k=length))

# ========================
# KLAVIATURALAR
# ========================
def main_menu_keyboard(user_id: int):
    builder = ReplyKeyboardBuilder()
    builder.button(text="🛍️ Katalog")
    builder.button(text="🛒 Savat")
    builder.button(text="📦 Buyurtmalarim")
    builder.button(text="📞 Aloqa")
    if is_admin(user_id):
        builder.button(text="👑 Admin panel")
    elif is_worker(user_id):
        builder.button(text="👨‍💼 Ishchi panel")
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)

def admin_menu_keyboard():
    builder = ReplyKeyboardBuilder()
    builder.button(text="➕ Kategoriya qo'shish")
    builder.button(text="➕ Mahsulot qo'shish")
    builder.button(text="✏️ Mahsulot tahrirlash")
    builder.button(text="🗑️ Mahsulot o'chirish")
    builder.button(text="🗑️ Kategoriya o'chirish")
    builder.button(text="📊 Barcha buyurtmalar")
    builder.button(text="👨‍💼 Ishchilar boshqaruvi")
    builder.button(text="🔙 Orqaga")
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)

def worker_menu_keyboard():
    builder = ReplyKeyboardBuilder()
    builder.button(text="➕ Mahsulot qo'shish")
    builder.button(text="✏️ Mahsulot tahrirlash")
    builder.button(text="🗑️ Mahsulot o'chirish")
    builder.button(text="📊 Buyurtmalar")
    builder.button(text="🔙 Orqaga")
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)

def cancel_keyboard():
    builder = ReplyKeyboardBuilder()
    builder.button(text="❌ Bekor qilish")
    return builder.as_markup(resize_keyboard=True)

# ========================
# /START
# ========================
@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    db.add_user(user_id, message.from_user.full_name, message.from_user.username)

    welcome_text = (
        f"👋 Xush kelibsiz!\n\n"
        f"🛒 Mahsulotlarimizni ko'rib buyurtma bering.\n"
        f"Quyidagi tugmalardan foydalaning:"
    )
    await message.answer(welcome_text, reply_markup=main_menu_keyboard(user_id))

# ========================
# ISHCHI KIRISHI (/worker)
# ========================
@dp.message(Command("worker"))
async def worker_login_start(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    if is_admin(user_id) or is_worker(user_id):
        await message.answer("✅ Siz allaqachon ishchi yoki admin sifatida kirgansiz!")
        return
    await message.answer(
        "🔐 Ishchi parolini kiriting:\n(Admindan oling)",
        reply_markup=cancel_keyboard()
    )
    await state.set_state(WorkerLoginStates.entering_password)

@dp.message(WorkerLoginStates.entering_password, F.text)
async def worker_login_check(message: types.Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("Bekor qilindi.", reply_markup=main_menu_keyboard(message.from_user.id))
        return

    success = db.use_worker_password(message.text.strip(), message.from_user.id)
    if success:
        await state.clear()
        await message.answer(
            "✅ Muvaffaqiyatli! Siz ishchi sifatida kirgansiz.\n"
            "Endi mahsulot qo'shish va tahrirlash imkoniyatingiz bor.",
            reply_markup=main_menu_keyboard(message.from_user.id)
        )
    else:
        await message.answer("❌ Parol noto'g'ri yoki allaqachon ishlatilgan. Qaytadan kiriting:")

# ========================
# KATALOG
# ========================
@dp.message(F.text == "🛍️ Katalog")
async def show_catalog(message: types.Message, state: FSMContext):
    await state.clear()
    categories = db.get_categories()

    if not categories:
        await message.answer("😔 Hozircha mahsulotlar yo'q.")
        return

    builder = InlineKeyboardBuilder()
    for cat in categories:
        size_icon = " 📏" if cat['has_sizes'] else ""
        builder.button(text=f"📁 {cat['name']}{size_icon}", callback_data=f"cat_{cat['id']}")
    builder.adjust(2)

    await message.answer(
        "📂 Kategoriyani tanlang:\n<i>(📏 — razmerlar mavjud)</i>",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )
    await state.set_state(OrderStates.choosing_category)

@dp.callback_query(F.data.regexp(r"^cat_\d+$"))
async def show_products(callback: types.CallbackQuery, state: FSMContext):
    cat_id = int(callback.data.split("_")[1])
    products = db.get_products_by_category(cat_id)
    cat = db.get_category(cat_id)

    if not products:
        await callback.answer("Bu kategoriyada mahsulot yo'q!", show_alert=True)
        return

    size_note = " (📏 razmer tanlanadi)" if cat['has_sizes'] else ""
    await callback.message.edit_text(
        f"📁 <b>{cat['name']}</b>{size_note}\n\nMahsulotni tanlang:",
        parse_mode="HTML"
    )

    for product in products:
        text = (
            f"🏷️ <b>{product['name']}</b>\n"
            f"💰 Narx: <b>{product['price']:,} so'm</b>\n"
        )
        if product['description']:
            text += f"📝 {product['description']}\n"
        if product.get('sizes'):
            preview = " | ".join(product['sizes'].split(","))
            text += f"📏 Razmerlar: <b>{preview}</b>\n"

        builder = InlineKeyboardBuilder()
        builder.button(text="🛒 Savatga", callback_data=f"add_{product['id']}")

        if product['photo_id']:
            await callback.message.answer_photo(
                photo=product['photo_id'],
                caption=text,
                reply_markup=builder.as_markup(),
                parse_mode="HTML"
            )
        else:
            await callback.message.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")

    builder_back = InlineKeyboardBuilder()
    builder_back.button(text="🔙 Kategoriyalar", callback_data="back_to_cats")
    await callback.message.answer("⬆️ Yuqoridagi mahsulotlar", reply_markup=builder_back.as_markup())
    await state.set_state(OrderStates.choosing_product)

@dp.callback_query(F.data == "back_to_cats")
async def back_to_categories(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.delete()
    await show_catalog(callback.message, state)

# ========================
# RAZMER TANLASH
# ========================
@dp.callback_query(F.data.startswith("add_"))
async def ask_size_or_add(callback: types.CallbackQuery, state: FSMContext):
    product_id = int(callback.data.split("_")[1])
    product = db.get_product(product_id)

    if product and product.get('sizes'):
        # Mahsulotning o'z razmerlarini tugma sifatida ko'rsatish
        sizes_list = product['sizes'].split(",")
        builder = InlineKeyboardBuilder()
        for sz in sizes_list:
            builder.button(text=sz.strip(), callback_data=f"size_{product_id}_{sz.strip()}")
        builder.button(text="❌ Bekor", callback_data="size_cancel")
        builder.adjust(4)

        await callback.message.answer(
            f"📏 <b>{product['name']}</b>\n\nRazmerni tanlang:",
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )
        await state.set_state(OrderStates.choosing_size)
    else:
        # Razmersiz — to'g'ridan savatga
        db.add_to_cart(callback.from_user.id, product_id, size=None)
        await callback.answer(f"✅ {product['name']} savatga qo'shildi!", show_alert=False)

@dp.callback_query(F.data == "size_cancel")
async def size_cancel(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.delete()
    await state.set_state(OrderStates.choosing_product)

@dp.callback_query(F.data.startswith("size_"), OrderStates.choosing_size)
async def confirm_size(callback: types.CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")   # size_<product_id>_<SIZE>
    product_id = int(parts[1])
    size = parts[2]

    db.add_to_cart(callback.from_user.id, product_id, size)
    product = db.get_product(product_id)

    await callback.answer(f"✅ {product['name']} ({size}) savatga qo'shildi!")
    await callback.message.delete()
    await state.set_state(OrderStates.choosing_product)

# ========================
# SAVAT
# ========================
@dp.message(F.text == "🛒 Savat")
async def show_cart(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    cart_items = db.get_cart(user_id)

    if not cart_items:
        await message.answer(
            "🛒 Savatingiz bo'sh.\n\n"
            "Mahsulot qo'shish uchun Katalogga o'ting."
        )
        return

    text = "🛒 <b>Savatingiz:</b>\n\n"
    total = 0
    builder = InlineKeyboardBuilder()

    for item in cart_items:
        subtotal = item['price'] * item['quantity']
        total += subtotal
        size_label = f" [{item['size']}]" if item.get('size') else ""
        text += (
            f"▫️ <b>{item['name']}</b>{size_label}\n"
            f"   {item['quantity']} × {item['price']:,} = <b>{subtotal:,} so'm</b>\n"
        )
        btn_label = f"❌ {item['name'][:15]}{size_label}"
        builder.button(text=btn_label, callback_data=f"rmv_{item['cart_id']}")

    # Chegirma hisoblash
    discount_amt, final_price, pct = calc_discount(total)
    text += f"\n💰 Jami: <b>{total:,} so'm</b>"
    if discount_amt > 0:
        text += (
            f"\n🎁 Chegirma ({pct}%): <b>-{discount_amt:,} so'm</b>"
            f"\n✅ To'lov: <b>{final_price:,} so'm</b>"
        )
    text += discount_hint(total)

    builder.adjust(1)
    builder.button(text="✅ Buyurtma berish", callback_data="checkout")
    builder.button(text="🗑️ Savatni tozalash", callback_data="clear_cart")

    await message.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")

@dp.callback_query(F.data.startswith("rmv_"))
async def remove_from_cart(callback: types.CallbackQuery, state: FSMContext):
    cart_id = int(callback.data.split("_")[1])
    db.remove_from_cart(cart_id)
    await callback.answer("❌ O'chirildi")
    await callback.message.delete()
    await show_cart(callback.message, state)

@dp.callback_query(F.data == "clear_cart")
async def clear_cart_cb(callback: types.CallbackQuery):
    db.clear_cart(callback.from_user.id)
    await callback.message.edit_text("🗑️ Savat tozalandi.")

# ========================
# BUYURTMA BERISH (CHECKOUT)
# ========================
@dp.callback_query(F.data == "checkout")
async def checkout_start(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer(
        "📝 Ismingizni kiriting:\nMasalan: Ahmadjon",
        reply_markup=cancel_keyboard()
    )
    await state.set_state(OrderStates.entering_name)

@dp.message(OrderStates.entering_name, F.text)
async def get_name(message: types.Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("❌ Bekor qilindi.", reply_markup=main_menu_keyboard(message.from_user.id))
        return
    await state.update_data(customer_name=message.text)
    await message.answer(
        "📞 Telefon raqamingizni yuboring:",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="📱 Raqamni yuborish", request_contact=True)],
                [KeyboardButton(text="❌ Bekor qilish")]
            ],
            resize_keyboard=True
        )
    )
    await state.set_state(OrderStates.entering_phone)

@dp.message(OrderStates.entering_phone)
async def get_phone(message: types.Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("❌ Bekor qilindi.", reply_markup=main_menu_keyboard(message.from_user.id))
        return
    phone = message.contact.phone_number if message.contact else message.text
    await state.update_data(phone=phone)
    await message.answer(
        "📍 Manzilingizni kiriting:\nMasalan: Toshkent, Chilonzor 5-kvartal, 12-uy",
        reply_markup=cancel_keyboard()
    )
    await state.set_state(OrderStates.entering_address)

@dp.message(OrderStates.entering_address, F.text)
async def get_address(message: types.Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("❌ Bekor qilindi.", reply_markup=main_menu_keyboard(message.from_user.id))
        return
    await state.update_data(address=message.text)

    builder = InlineKeyboardBuilder()
    builder.button(text="💵 Naqd", callback_data="pay_cash")
    builder.button(text="💳 Payme", callback_data="pay_payme")
    builder.button(text="💳 Click", callback_data="pay_click")
    builder.adjust(1)

    await message.answer("💳 To'lov usulini tanlang:", reply_markup=builder.as_markup())
    await state.set_state(OrderStates.choosing_payment)

@dp.callback_query(F.data.startswith("pay_"), OrderStates.choosing_payment)
async def process_payment(callback: types.CallbackQuery, state: FSMContext):
    payment_map = {
        "pay_cash": "💵 Naqd",
        "pay_payme": "💳 Payme",
        "pay_click": "💳 Click"
    }
    payment = payment_map.get(callback.data, "Noma'lum")
    data = await state.get_data()
    user_id = callback.from_user.id
    cart_items = db.get_cart(user_id)

    if not cart_items:
        await callback.answer("Savat bo'sh!", show_alert=True)
        await state.clear()
        return

    gross = sum(item['price'] * item['quantity'] for item in cart_items)
    discount_amt, final_price, pct = calc_discount(gross)

    order_id = db.create_order(
        user_id=user_id,
        customer_name=data['customer_name'],
        phone=data['phone'],
        address=data['address'],
        payment=payment,
        items=cart_items,
        total=final_price,
        discount_pct=pct,
        discount_amt=discount_amt
    )

    # Chegirma satri
    if discount_amt > 0:
        disc_line = (
            f"\n💰 Asl narx: {gross:,} so'm"
            f"\n🎁 Chegirma ({pct}%): -{discount_amt:,} so'm"
            f"\n✅ To'lov: <b>{final_price:,} so'm</b>"
        )
    else:
        disc_line = f"\n💰 Jami: <b>{gross:,} so'm</b>"

    confirm_text = (
        f"✅ <b>Buyurtmangiz qabul qilindi!</b>\n\n"
        f"🔢 Buyurtma №{order_id}\n"
        f"👤 {data['customer_name']}\n"
        f"📞 {data['phone']}\n"
        f"📍 {data['address']}\n"
        f"💳 {payment}"
        f"{disc_line}\n\n"
        f"📦 Tez orada siz bilan bog'lanamiz!"
    )
    await callback.message.answer(
        confirm_text,
        reply_markup=main_menu_keyboard(user_id),
        parse_mode="HTML"
    )

    # Admin/worker larga xabar
    items_text = "\n".join([
        f"  • {item['name']}"
        f"{' [' + item['size'] + ']' if item.get('size') else ''}"
        f" ×{item['quantity']} = {item['price'] * item['quantity']:,} so'm"
        for item in cart_items
    ])

    disc_admin = f"\n🎁 Chegirma ({pct}%): -{discount_amt:,} so'm" if discount_amt > 0 else ""
    admin_text = (
        f"🆕 <b>YANGI BUYURTMA №{order_id}</b>\n\n"
        f"👤 Mijoz: {data['customer_name']}\n"
        f"📞 Tel: {data['phone']}\n"
        f"📍 Manzil: {data['address']}\n"
        f"💳 To'lov: {payment}\n\n"
        f"🛒 Mahsulotlar:\n{items_text}\n"
        f"\n💰 Asl narx: {gross:,} so'm"
        f"{disc_admin}\n"
        f"✅ <b>To'lov: {final_price:,} so'm</b>\n"
        f"🆔 Telegram ID: {user_id}"
    )

    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Qabul qilindi", callback_data=f"order_accept_{order_id}")
    builder.button(text="❌ Bekor qilish", callback_data=f"order_cancel_{order_id}")
    builder.adjust(2)

    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, admin_text, reply_markup=builder.as_markup(), parse_mode="HTML")
        except Exception as e:
            logger.error(f"Adminga xabar yuborishda xato: {e}")

    # Ishchilarga ham yangi buyurtma haqida xabar
    workers = db.get_workers()
    worker_builder = InlineKeyboardBuilder()
    worker_builder.button(text="✅ Qabul qilindi", callback_data=f"worder_accept_{order_id}")
    worker_builder.button(text="🚚 Yetkazildi", callback_data=f"worder_deliver_{order_id}")
    worker_builder.button(text="❌ Bekor qilish", callback_data=f"worder_cancel_{order_id}")
    worker_builder.adjust(2)
    for worker in workers:
        try:
            await bot.send_message(
                worker['telegram_id'],
                admin_text,
                reply_markup=worker_builder.as_markup(),
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Ishchiga xabar yuborishda xato: {e}")

    db.clear_cart(user_id)
    await state.clear()

# Buyurtma boshqaruvi (admin)
@dp.callback_query(F.data.startswith("order_accept_"))
async def order_accept(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    order_id = int(callback.data.split("_")[2])
    db.update_order_status(order_id, "accepted")
    order = db.get_order(order_id)
    if order:
        try:
            await bot.send_message(
                order['user_id'],
                f"✅ Buyurtma №{order_id} qabul qilindi!\n"
                f"Tez orada yetkazib beramiz. Rahmat! 🙏"
            )
        except:
            pass
    await callback.message.edit_text(callback.message.text + "\n\n✅ QABUL QILINDI", parse_mode="HTML")

@dp.callback_query(F.data.startswith("order_cancel_"))
async def order_cancel(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    order_id = int(callback.data.split("_")[2])
    db.update_order_status(order_id, "cancelled")
    order = db.get_order(order_id)
    if order:
        try:
            await bot.send_message(
                order['user_id'],
                f"❌ Buyurtma №{order_id} bekor qilindi.\n"
                f"Qo'shimcha ma'lumot uchun biz bilan bog'laning."
            )
        except:
            pass
    await callback.message.edit_text(callback.message.text + "\n\n❌ BEKOR QILINDI", parse_mode="HTML")

# ========================
# BUYURTMALAR TARIXI
# ========================
@dp.message(F.text == "📦 Buyurtmalarim")
async def my_orders(message: types.Message):
    orders = db.get_user_orders(message.from_user.id)
    if not orders:
        await message.answer("📦 Sizda hali buyurtma yo'q.")
        return

    status_emoji = {"pending": "⏳", "accepted": "✅", "cancelled": "❌", "delivered": "🚚"}
    text = "📦 <b>Buyurtmalaringiz:</b>\n\n"
    for order in orders[-10:]:
        emoji = status_emoji.get(order['status'], "❓")
        disc_line = f" (chegirma -{order['discount_amt']:,})" if order.get('discount_amt') else ""
        text += (
            f"{emoji} <b>№{order['id']}</b> — {order['total']:,} so'm{disc_line}\n"
            f"📅 {order['created_at'][:10]}\n\n"
        )
    await message.answer(text, parse_mode="HTML")

# ========================
# ALOQA
# ========================
@dp.message(F.text == "📞 Aloqa")
async def contact(message: types.Message):
    await message.answer(
        "📞 <b>Biz bilan bog'laning:</b>\n\n"
        "📱 Tel: +998 99 7420160\n"
        "📱 Telegram: @Buyukkids1\n"
        "🕐 Ish vaqti: 9:00 - 21:00\n\n"
        "Savollaringiz bo'lsa yozing!",
        parse_mode="HTML"
    )

# ========================
# ISHCHI PANEL
# ========================
@dp.message(F.text == "👨‍💼 Ishchi panel")
async def worker_panel(message: types.Message, state: FSMContext):
    if not is_worker(message.from_user.id):
        await message.answer("❌ Ruxsat yo'q!")
        return
    await state.clear()
    await message.answer(
        "👨‍💼 <b>Ishchi panel</b>\n\nNimani qilmoqchisiz?",
        reply_markup=worker_menu_keyboard(),
        parse_mode="HTML"
    )

# ========================
# ADMIN PANEL
# ========================
@dp.message(F.text == "👑 Admin panel")
async def admin_panel(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("❌ Ruxsat yo'q!")
        return
    await state.clear()
    await message.answer(
        "👑 <b>Admin panel</b>",
        reply_markup=admin_menu_keyboard(),
        parse_mode="HTML"
    )

@dp.message(F.text == "🔙 Orqaga")
async def back_to_main(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("Bosh menyu:", reply_markup=main_menu_keyboard(message.from_user.id))

# ========================
# KATEGORIYA QO'SHISH (Admin)
# ========================
@dp.message(F.text == "➕ Kategoriya qo'shish")
async def add_category_start(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await message.answer(
        "📁 Kategoriya nomini kiriting:\n(Masalan: Bolalar kiyimi, Aksessuarlar)",
        reply_markup=cancel_keyboard()
    )
    await state.set_state(AdminStates.adding_category_name)

@dp.message(AdminStates.adding_category_name, F.text)
async def get_category_name(message: types.Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("Bekor qilindi.", reply_markup=admin_menu_keyboard())
        return
    await state.update_data(cat_name=message.text)

    builder = InlineKeyboardBuilder()
    builder.button(text="📏 Ha, razmer kerak", callback_data="cat_sizes_yes")
    builder.button(text="🚫 Yo'q, razmer shart emas", callback_data="cat_sizes_no")
    builder.adjust(1)

    await message.answer(
        f"📁 <b>{message.text}</b>\n\n"
        f"Bu kategoriyada mahsulotlar uchun razmer (XS/S/M/L/XL...) so'rash kerakmi?",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )
    await state.set_state(AdminStates.adding_category_sizes)

@dp.callback_query(F.data.in_({"cat_sizes_yes", "cat_sizes_no"}), AdminStates.adding_category_sizes)
async def save_category(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    has_sizes = callback.data == "cat_sizes_yes"
    db.add_category(data['cat_name'], has_sizes)
    size_note = "📏 Razmer bilan" if has_sizes else "🚫 Razmersiz"
    await callback.message.edit_text(
        f"✅ '{data['cat_name']}' kategoriyasi qo'shildi!\n{size_note}"
    )
    await callback.message.answer("Davom etamiz:", reply_markup=admin_menu_keyboard())
    await state.clear()

# ========================
# MAHSULOT QO'SHISH (Admin & Worker)
# ========================
@dp.message(F.text == "➕ Mahsulot qo'shish")
async def add_product_start(message: types.Message, state: FSMContext):
    if not is_worker(message.from_user.id):
        return
    categories = db.get_categories()
    if not categories:
        await message.answer("❗ Avval kategoriya qo'shing!")
        return

    builder = InlineKeyboardBuilder()
    for cat in categories:
        size_icon = " 📏" if cat['has_sizes'] else ""
        builder.button(text=f"{cat['name']}{size_icon}", callback_data=f"admin_cat_{cat['id']}")
    builder.adjust(2)

    await message.answer(
        "📁 Mahsulot uchun kategoriyani tanlang:",
        reply_markup=builder.as_markup()
    )
    await state.set_state(AdminStates.choosing_category_for_product)

@dp.callback_query(F.data.startswith("admin_cat_"), AdminStates.choosing_category_for_product)
async def admin_choose_category(callback: types.CallbackQuery, state: FSMContext):
    cat_id = int(callback.data.split("_")[2])
    await state.update_data(category_id=cat_id)
    await callback.message.answer("🏷️ Mahsulot nomini kiriting:", reply_markup=cancel_keyboard())
    await state.set_state(AdminStates.adding_product_name)

@dp.message(AdminStates.adding_product_name, F.text)
async def get_product_name(message: types.Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        menu = admin_menu_keyboard() if is_admin(message.from_user.id) else worker_menu_keyboard()
        await message.answer("Bekor qilindi.", reply_markup=menu)
        return
    await state.update_data(product_name=message.text)
    await message.answer("💰 Narxini kiriting (faqat raqam, so'mda):\nMasalan: 85000")
    await state.set_state(AdminStates.adding_product_price)

@dp.message(AdminStates.adding_product_price, F.text)
async def get_product_price(message: types.Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        menu = admin_menu_keyboard() if is_admin(message.from_user.id) else worker_menu_keyboard()
        await message.answer("Bekor qilindi.", reply_markup=menu)
        return
    try:
        price = int(message.text.replace(" ", "").replace(",", ""))
    except ValueError:
        await message.answer("❗ Faqat raqam kiriting! Masalan: 85000")
        return
    await state.update_data(product_price=price)
    await message.answer("📝 Tavsif kiriting (yoki /skip yozing):")
    await state.set_state(AdminStates.adding_product_description)

@dp.message(AdminStates.adding_product_description, F.text)
async def get_product_description(message: types.Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        menu = admin_menu_keyboard() if is_admin(message.from_user.id) else worker_menu_keyboard()
        await message.answer("Bekor qilindi.", reply_markup=menu)
        return
    desc = "" if message.text == "/skip" else message.text
    await state.update_data(product_description=desc)

    # Kategoriya razmerli bo'lsa — razmerlarni so'raymiz
    data = await state.get_data()
    cat = db.get_category(data['category_id'])
    if cat and cat['has_sizes']:
        await message.answer(
            "📏 Mavjud razmerlarni kiriting (vergul bilan ajrating):\n\n"
            "Masalan: <code>86, 92, 98, 104, 110, 116</code>\n\n"
            "Yoki /skip yozing (keyinchalik qo'shish uchun)",
            reply_markup=cancel_keyboard(),
            parse_mode="HTML"
        )
        await state.set_state(AdminStates.adding_product_sizes)
    else:
        await message.answer(
            "📸 Mahsulot rasmini yuboring (yoki /skip yozing):",
            reply_markup=cancel_keyboard()
        )
        await state.set_state(AdminStates.adding_product_photo)

@dp.message(AdminStates.adding_product_sizes, F.text)
async def get_product_sizes(message: types.Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        menu = admin_menu_keyboard() if is_admin(message.from_user.id) else worker_menu_keyboard()
        await message.answer("Bekor qilindi.", reply_markup=menu)
        return

    if message.text == "/skip":
        sizes_str = None
    else:
        # Tozalash: 86, 92, 98 → "86,92,98"
        raw = message.text.replace(" ", "").replace("،", ",").replace(";", ",")
        parts = [s.strip() for s in raw.split(",") if s.strip()]
        if not parts:
            await message.answer("❗ Kamida bitta razmer kiriting! Masalan: 86, 92, 98")
            return
        sizes_str = ",".join(parts)

    await state.update_data(product_sizes=sizes_str)

    preview = " | ".join(sizes_str.split(",")) if sizes_str else "—"
    await message.answer(
        f"✅ Razmerlar: <b>{preview}</b>\n\n"
        f"📸 Mahsulot rasmini yuboring (yoki /skip yozing):",
        reply_markup=cancel_keyboard(),
        parse_mode="HTML"
    )
    await state.set_state(AdminStates.adding_product_photo)

@dp.message(AdminStates.adding_product_photo)
async def get_product_photo(message: types.Message, state: FSMContext):
    if message.text and message.text == "❌ Bekor qilish":
        await state.clear()
        menu = admin_menu_keyboard() if is_admin(message.from_user.id) else worker_menu_keyboard()
        await message.answer("Bekor qilindi.", reply_markup=menu)
        return
    photo_id = None
    if message.photo:
        photo_id = message.photo[-1].file_id

    data = await state.get_data()
    sizes_str = data.get('product_sizes', None)

    db.add_product(
        name=data['product_name'],
        price=data['product_price'],
        description=data['product_description'],
        category_id=data['category_id'],
        photo_id=photo_id,
        sizes=sizes_str
    )

    size_note = ""
    if sizes_str:
        preview = " | ".join(sizes_str.split(","))
        size_note = f"\n📏 Razmerlar: {preview}"

    menu = admin_menu_keyboard() if is_admin(message.from_user.id) else worker_menu_keyboard()
    await message.answer(
        f"✅ '<b>{data['product_name']}</b>' qo'shildi!\n"
        f"💰 Narxi: {data['product_price']:,} so'm"
        f"{size_note}",
        reply_markup=menu,
        parse_mode="HTML"
    )
    await state.clear()

# ========================
# MAHSULOT TAHRIRLASH (Admin & Worker)
# ========================
@dp.message(F.text == "✏️ Mahsulot tahrirlash")
async def edit_product_start(message: types.Message, state: FSMContext):
    if not is_worker(message.from_user.id):
        return
    products = db.get_all_products()
    if not products:
        await message.answer("Mahsulotlar yo'q.")
        return

    builder = InlineKeyboardBuilder()
    for p in products:
        builder.button(
            text=f"✏️ {p['name']} ({p['price']:,})",
            callback_data=f"edit_prod_{p['id']}"
        )
    builder.adjust(1)
    await message.answer("Tahrirlash uchun mahsulotni tanlang:", reply_markup=builder.as_markup())
    await state.set_state(AdminStates.editing_product_select)

@dp.callback_query(F.data.startswith("edit_prod_"), AdminStates.editing_product_select)
async def edit_product_select(callback: types.CallbackQuery, state: FSMContext):
    product_id = int(callback.data.split("_")[2])
    product = db.get_product(product_id)
    await state.update_data(edit_product_id=product_id)

    builder = InlineKeyboardBuilder()
    builder.button(text="🏷️ Nomini o'zgartirish", callback_data="edit_field_name")
    builder.button(text="💰 Narxini o'zgartirish", callback_data="edit_field_price")
    builder.button(text="📝 Tavsifini o'zgartirish", callback_data="edit_field_description")
    builder.button(text="📸 Rasmini o'zgartirish", callback_data="edit_field_photo")
    builder.button(text="❌ Bekor", callback_data="edit_cancel")
    builder.adjust(2)

    text = (
        f"✏️ <b>{product['name']}</b>\n"
        f"💰 Narx: {product['price']:,} so'm\n"
        f"📝 Tavsif: {product['description'] or '—'}\n\n"
        f"Nimani o'zgartirmoqchisiz?"
    )
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await state.set_state(AdminStates.editing_product_field)

@dp.callback_query(F.data == "edit_cancel")
async def edit_cancel(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Bekor qilindi.")

@dp.callback_query(F.data.startswith("edit_field_"), AdminStates.editing_product_field)
async def edit_field_select(callback: types.CallbackQuery, state: FSMContext):
    field = callback.data.replace("edit_field_", "")
    await state.update_data(edit_field=field)

    if field == "photo":
        await callback.message.answer(
            "📸 Yangi rasmni yuboring:",
            reply_markup=cancel_keyboard()
        )
        await state.set_state(AdminStates.editing_product_photo_new)
    else:
        prompts = {
            "name": "🏷️ Yangi nomini kiriting:",
            "price": "💰 Yangi narxini kiriting (raqam):",
            "description": "📝 Yangi tavsifini kiriting (yoki /skip):"
        }
        await callback.message.answer(prompts[field], reply_markup=cancel_keyboard())
        await state.set_state(AdminStates.editing_product_value)

@dp.message(AdminStates.editing_product_value, F.text)
async def edit_product_value(message: types.Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        menu = admin_menu_keyboard() if is_admin(message.from_user.id) else worker_menu_keyboard()
        await message.answer("Bekor qilindi.", reply_markup=menu)
        return

    data = await state.get_data()
    product_id = data['edit_product_id']
    field = data['edit_field']

    if field == "price":
        try:
            value = int(message.text.replace(" ", "").replace(",", ""))
        except ValueError:
            await message.answer("❗ Faqat raqam kiriting!")
            return
    elif field == "description" and message.text == "/skip":
        value = ""
    else:
        value = message.text

    db.update_product_field(product_id, field, value)
    menu = admin_menu_keyboard() if is_admin(message.from_user.id) else worker_menu_keyboard()
    await message.answer(f"✅ Mahsulot yangilandi!", reply_markup=menu)
    await state.clear()

@dp.message(AdminStates.editing_product_photo_new)
async def edit_product_photo(message: types.Message, state: FSMContext):
    if message.text and message.text == "❌ Bekor qilish":
        await state.clear()
        menu = admin_menu_keyboard() if is_admin(message.from_user.id) else worker_menu_keyboard()
        await message.answer("Bekor qilindi.", reply_markup=menu)
        return
    if not message.photo:
        await message.answer("❗ Rasm yuboring!")
        return

    data = await state.get_data()
    db.update_product_field(data['edit_product_id'], 'photo_id', message.photo[-1].file_id)
    menu = admin_menu_keyboard() if is_admin(message.from_user.id) else worker_menu_keyboard()
    await message.answer("✅ Rasm yangilandi!", reply_markup=menu)
    await state.clear()

# ========================
# MAHSULOT O'CHIRISH (Admin & Worker)
# ========================
@dp.message(F.text == "🗑️ Mahsulot o'chirish")
async def delete_product_start(message: types.Message, state: FSMContext):
    if not is_worker(message.from_user.id):
        return
    products = db.get_all_products()
    if not products:
        await message.answer("Mahsulotlar yo'q.")
        return

    builder = InlineKeyboardBuilder()
    for p in products:
        builder.button(text=f"❌ {p['name']} ({p['price']:,})", callback_data=f"del_prod_{p['id']}")
    builder.adjust(1)
    await message.answer("O'chiriladigan mahsulotni tanlang:", reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith("del_prod_"))
async def delete_product(callback: types.CallbackQuery):
    if not is_worker(callback.from_user.id):
        return
    product_id = int(callback.data.split("_")[2])
    product = db.get_product(product_id)
    db.delete_product(product_id)
    await callback.message.edit_text(f"✅ '{product['name']}' o'chirildi!")

# ========================
# KATEGORIYA O'CHIRISH (faqat Admin)
# ========================
@dp.message(F.text == "🗑️ Kategoriya o'chirish")
async def delete_category_start(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    categories = db.get_categories()
    if not categories:
        await message.answer("Kategoriyalar yo'q.")
        return

    builder = InlineKeyboardBuilder()
    for cat in categories:
        builder.button(text=f"❌ {cat['name']}", callback_data=f"del_cat_{cat['id']}")
    builder.adjust(1)
    await message.answer("O'chiriladigan kategoriyani tanlang:", reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith("del_cat_"))
async def delete_category(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    cat_id = int(callback.data.split("_")[2])
    cat_name = db.get_category_name(cat_id)
    db.delete_category(cat_id)
    await callback.message.edit_text(f"✅ '{cat_name}' kategoriyasi o'chirildi!")

# ========================
# BUYURTMALAR (Ishchi) — ko'rish va status o'zgartirish
# ========================
@dp.message(F.text == "📊 Buyurtmalar")
async def worker_orders(message: types.Message):
    if not is_worker(message.from_user.id):
        return
    orders = db.get_all_orders()
    if not orders:
        await message.answer("📭 Hozircha buyurtmalar yo'q.")
        return

    status_map = {
        "pending":   "⏳ Kutmoqda",
        "accepted":  "✅ Qabul qilindi",
        "delivered": "🚚 Yetkazildi",
        "cancelled": "❌ Bekor qilindi",
    }
    text = "📊 <b>Oxirgi buyurtmalar:</b>\n\n"
    builder = InlineKeyboardBuilder()

    for order in orders[:20]:
        status_label = status_map.get(order['status'], "❓")
        text += (
            f"🔢 <b>№{order['id']}</b> | {order['customer_name']} | "
            f"{order['total']:,} so'm | {status_label}\n"
            f"📅 {order['created_at'][:10]}\n"
        )
        builder.button(
            text=f"№{order['id']} — batafsil",
            callback_data=f"worder_detail_{order['id']}"
        )

    builder.adjust(1)
    await message.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")


@dp.callback_query(F.data.startswith("worder_detail_"))
async def worker_order_detail(callback: types.CallbackQuery):
    if not is_worker(callback.from_user.id):
        return
    order_id = int(callback.data.split("_")[2])
    order = db.get_order(order_id)
    items = db.get_order_items(order_id)

    if not order:
        await callback.answer("Buyurtma topilmadi!", show_alert=True)
        return

    status_map = {
        "pending":   "⏳ Kutmoqda",
        "accepted":  "✅ Qabul qilindi",
        "delivered": "🚚 Yetkazildi",
        "cancelled": "❌ Bekor qilindi",
    }
    items_text = "\n".join([
        f"  • {item['product_name']}"
        f"{' [' + item['size'] + ']' if item.get('size') else ''}"
        f" ×{item['quantity']} = {item['price'] * item['quantity']:,} so'm"
        for item in items
    ])
    disc_line = ""
    if order.get('discount_amt') and order['discount_amt'] > 0:
        disc_line = f"\n🎁 Chegirma ({order['discount_pct']}%): -{order['discount_amt']:,} so'm"

    text = (
        f"📦 <b>Buyurtma №{order_id}</b>\n\n"
        f"👤 Mijoz: {order['customer_name']}\n"
        f"📞 Tel: {order['phone']}\n"
        f"📍 Manzil: {order['address']}\n"
        f"💳 To'lov: {order['payment']}\n"
        f"📅 Sana: {order['created_at'][:16]}\n"
        f"📊 Status: {status_map.get(order['status'], '❓')}\n\n"
        f"🛒 Mahsulotlar:\n{items_text}"
        f"{disc_line}\n"
        f"✅ <b>Jami: {order['total']:,} so'm</b>"
    )

    builder = InlineKeyboardBuilder()
    if order['status'] == "pending":
        builder.button(text="✅ Qabul qilish", callback_data=f"worder_accept_{order_id}")
        builder.button(text="❌ Bekor qilish", callback_data=f"worder_cancel_{order_id}")
    if order['status'] == "accepted":
        builder.button(text="🚚 Yetkazildi", callback_data=f"worder_deliver_{order_id}")
        builder.button(text="❌ Bekor qilish", callback_data=f"worder_cancel_{order_id}")
    builder.adjust(2)

    await callback.message.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()


@dp.callback_query(F.data.startswith("worder_accept_"))
async def worker_order_accept(callback: types.CallbackQuery):
    if not is_worker(callback.from_user.id):
        return
    order_id = int(callback.data.split("_")[2])
    db.update_order_status(order_id, "accepted")
    order = db.get_order(order_id)
    if order:
        try:
            await bot.send_message(
                order['user_id'],
                f"✅ Buyurtma №{order_id} qabul qilindi!\nTez orada yetkazib beramiz. Rahmat! 🙏"
            )
        except:
            pass
    await callback.message.edit_text(
        callback.message.text + "\n\n✅ STATUS: QABUL QILINDI",
        parse_mode="HTML"
    )
    await callback.answer("✅ Qabul qilindi!")


@dp.callback_query(F.data.startswith("worder_deliver_"))
async def worker_order_deliver(callback: types.CallbackQuery):
    if not is_worker(callback.from_user.id):
        return
    order_id = int(callback.data.split("_")[2])
    db.update_order_status(order_id, "delivered")
    order = db.get_order(order_id)
    if order:
        try:
            await bot.send_message(
                order['user_id'],
                f"🚚 Buyurtma №{order_id} yetkazib berildi!\nXarid uchun rahmat! 🙏"
            )
        except:
            pass
    await callback.message.edit_text(
        callback.message.text + "\n\n🚚 STATUS: YETKAZILDI",
        parse_mode="HTML"
    )
    await callback.answer("🚚 Yetkazildi deb belgilandi!")


@dp.callback_query(F.data.startswith("worder_cancel_"))
async def worker_order_cancel(callback: types.CallbackQuery):
    if not is_worker(callback.from_user.id):
        return
    order_id = int(callback.data.split("_")[2])
    db.update_order_status(order_id, "cancelled")
    order = db.get_order(order_id)
    if order:
        try:
            await bot.send_message(
                order['user_id'],
                f"❌ Buyurtma №{order_id} bekor qilindi.\nQo'shimcha ma'lumot uchun biz bilan bog'laning."
            )
        except:
            pass
    await callback.message.edit_text(
        callback.message.text + "\n\n❌ STATUS: BEKOR QILINDI",
        parse_mode="HTML"
    )
    await callback.answer("❌ Bekor qilindi!")


# ========================
# BARCHA BUYURTMALAR (faqat Admin)
# ========================
@dp.message(F.text == "📊 Barcha buyurtmalar")
async def all_orders(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    orders = db.get_all_orders()
    if not orders:
        await message.answer("Buyurtmalar yo'q.")
        return

    status_map = {"pending": "⏳", "accepted": "✅", "cancelled": "❌", "delivered": "🚚"}
    text = "📊 <b>Oxirgi buyurtmalar:</b>\n\n"
    for order in orders[:20]:
        emoji = status_map.get(order['status'], "❓")
        text += (
            f"{emoji} №{order['id']} | {order['customer_name']} | "
            f"{order['total']:,} so'm | {order['created_at'][:10]}\n"
        )
    await message.answer(text, parse_mode="HTML")

# ========================
# ISHCHILAR BOSHQARUVI (faqat Admin)
# ========================
@dp.message(F.text == "👨‍💼 Ishchilar boshqaruvi")
async def workers_management(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.clear()

    workers = db.get_workers()
    passwords = db.get_worker_passwords()

    text = "👨‍💼 <b>Ishchilar boshqaruvi</b>\n\n"

    # Faol ishchilar
    if workers:
        text += "✅ <b>Faol ishchilar:</b>\n"
        for w in workers:
            uname = f"@{w['username']}" if w.get('username') else "—"
            text += f"  • {w['full_name']} ({uname}) | ID: {w['telegram_id']}\n"
    else:
        text += "👤 Faol ishchilar yo'q\n"

    # So'ngi parollar
    text += "\n🔑 <b>So'ngi parollar:</b>\n"
    for pw in passwords[:10]:
        status = f"✅ {pw['used_by_name']}" if pw['is_used'] else "⏳ Kutmoqda"
        text += f"  <code>{pw['password']}</code> — {status}\n"

    builder = InlineKeyboardBuilder()
    builder.button(text="➕ Yangi parol yaratish", callback_data="create_worker_pwd")
    if workers:
        builder.button(text="🗑️ Ishchini o'chirish", callback_data="remove_worker_start")
    builder.adjust(1)

    await message.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")

@dp.callback_query(F.data == "create_worker_pwd")
async def create_worker_pwd(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    password = gen_password(8)
    db.create_worker_password(password, callback.from_user.id)
    await callback.answer()
    await callback.message.answer(
        f"✅ Yangi ishchi paroli yaratildi:\n\n"
        f"🔑 <code>{password}</code>\n\n"
        f"Bu parolni ishchiga yuboring. U /worker komandasi orqali kiradi.\n"
        f"⚠️ Parol faqat bir marta ishlatiladi!",
        parse_mode="HTML"
    )

@dp.callback_query(F.data == "remove_worker_start")
async def remove_worker_start(callback: types.CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    workers = db.get_workers()
    if not workers:
        await callback.answer("Ishchilar yo'q!", show_alert=True)
        return

    builder = InlineKeyboardBuilder()
    for w in workers:
        builder.button(
            text=f"❌ {w['full_name']}",
            callback_data=f"fire_worker_{w['telegram_id']}"
        )
    builder.adjust(1)
    await callback.message.answer("O'chiriladigan ishchini tanlang:", reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith("fire_worker_"))
async def fire_worker(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    worker_tid = int(callback.data.split("_")[2])
    worker = db.get_user(worker_tid)
    db.remove_worker(worker_tid)
    name = worker['full_name'] if worker else str(worker_tid)
    await callback.message.edit_text(f"✅ {name} ishchilar ro'yxatidan chiqarildi.")
    try:
        await bot.send_message(
            worker_tid,
            "ℹ️ Sizning ishchi huquqlaringiz bekor qilindi."
        )
    except:
        pass

# ========================
# MAIN
# ========================
async def main():
    db.init_db()
    logger.info("Bot ishga tushmoqda...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

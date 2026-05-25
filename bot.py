#!/usr/bin/env python3
"""
Chakana savdo Telegram boti — yangilangan versiya
Rollar: admin | worker | user
Yangiliklar: dastavka turi, oylik/davr/dastavka hisoboti
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

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_IDS = [286262755]
DB_PATH   = os.getenv("DB_PATH", "shop.db")

SIZES              = ["XS", "S", "M", "L", "XL", "XXL", "3XL"]
DISCOUNT_TIER1_LIMIT = 500_000
DISCOUNT_TIER1_PCT   = 5
DISCOUNT_TIER2_PCT   = 10

# Dastavka turlari
DELIVERY_TYPES = {
    "del1": "📍 Qorasув bo'ylab — Bepul (haftada 2 marta)",
    "del2": "🚚 Samarkand ichida — Kelishilgan narxda",
    "del3": "⚡ Tezkor (Yandex Taxi) — Mijoz hisobidan",
}

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

bot     = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp      = Dispatcher(storage=storage)
db      = Database(DB_PATH)

# ══════════════════════════════════════
# STATES
# ══════════════════════════════════════
class OrderStates(StatesGroup):
    choosing_category  = State()
    choosing_product   = State()
    choosing_size      = State()
    in_cart            = State()
    entering_name      = State()
    entering_phone     = State()
    entering_address   = State()
    choosing_delivery  = State()
    choosing_payment   = State()
    searching_product  = State()

class WorkerLoginStates(StatesGroup):
    entering_password = State()

class AdminStates(StatesGroup):
    adding_category_name       = State()
    adding_category_sizes      = State()
    choosing_category_for_product = State()
    adding_product_name        = State()
    adding_product_price       = State()
    adding_product_description = State()
    adding_product_sizes       = State()
    adding_product_photo       = State()
    editing_product_select     = State()
    editing_product_field      = State()
    editing_product_value      = State()
    editing_product_photo_new  = State()
    deleting_product           = State()
    deleting_category          = State()
    creating_worker_password   = State()
    removing_worker            = State()

class ReportStates(StatesGroup):
    entering_date_from = State()
    entering_date_to   = State()

# ══════════════════════════════════════
# HELPERS
# ══════════════════════════════════════
def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

def is_worker(user_id: int) -> bool:
    return db.get_user_role(user_id) in ('worker', 'admin') or is_admin(user_id)

def calc_discount(total: int):
    if total <= 0:
        return 0, total, 0
    pct      = DISCOUNT_TIER2_PCT if total >= DISCOUNT_TIER1_LIMIT else DISCOUNT_TIER1_PCT
    discount = int(total * pct / 100)
    return discount, total - discount, pct

def discount_hint(total: int) -> str:
    if total < DISCOUNT_TIER1_LIMIT:
        remaining = DISCOUNT_TIER1_LIMIT - total
        return f"\n\n💡 Yana <b>{remaining:,} so'm</b> xarid qilsangiz, chegirma <b>{DISCOUNT_TIER2_PCT}%</b> ga ko'tariladi!"
    return ""

def gen_password(length=8) -> str:
    chars = string.ascii_uppercase + string.digits
    return ''.join(random.choices(chars, k=length))

# ══════════════════════════════════════
# KEYBOARDS
# ══════════════════════════════════════
def main_menu_keyboard(user_id: int):
    builder = ReplyKeyboardBuilder()
    builder.button(text="🛍️ Katalog")
    cart_items  = db.get_cart(user_id)
    cart_count  = sum(item['quantity'] for item in cart_items) if cart_items else 0
    cart_label  = f"🛒 Savat ({cart_count})" if cart_count > 0 else "🛒 Savat"
    builder.button(text=cart_label)
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
    builder.button(text="📈 Hisobotlar")
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

def delivery_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="📍 Qorasув bo'ylab (Bepul)", callback_data="delivery_del1")
    builder.button(text="🚚 Samarkand ichida",         callback_data="delivery_del2")
    builder.button(text="⚡ Tezkor (Yandex Taxi)",     callback_data="delivery_del3")
    builder.adjust(1)
    return builder.as_markup()

# ══════════════════════════════════════
# START
# ══════════════════════════════════════
@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    db.add_user(user_id, message.from_user.full_name, message.from_user.username)
    await message.answer(
        "👋 Xush kelibsiz!\n\n🛒 Mahsulotlarimizni ko'rib buyurtma bering.\nQuyidagi tugmalardan foydalaning:",
        reply_markup=main_menu_keyboard(user_id)
    )

@dp.message(Command("worker"))
async def worker_login_start(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    if is_admin(user_id) or is_worker(user_id):
        await message.answer("✅ Siz allaqachon ishchi yoki admin sifatida kirgansiz!")
        return
    await message.answer("🔐 Ishchi parolini kiriting:", reply_markup=cancel_keyboard())
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
        await message.answer("✅ Muvaffaqiyatli! Siz ishchi sifatida kirgansiz.", reply_markup=main_menu_keyboard(message.from_user.id))
    else:
        await message.answer("❌ Parol noto'g'ri. Qaytadan kiriting:")

# ══════════════════════════════════════
# KATALOG
# ══════════════════════════════════════
@dp.message(F.text == "🛍️ Katalog")
async def show_catalog(message: types.Message, state: FSMContext):
    await state.clear()
    categories = db.get_categories()
    if not categories:
        await message.answer("😔 Hozircha mahsulotlar yo'q.")
        return

    # Kategoriya nomi bo'yicha emoji avtomatik
    def cat_emoji(name: str) -> str:
        n = name.lower()
        if any(x in n for x in ['basseyn','havuz','suv']): return "🏊"
        if any(x in n for x in ['kiyim','bolalar','libos']): return "👕"
        if any(x in n for x in ['obuf','poyabzal','botinka']): return "👟"
        if any(x in n for x in ['velosiped','velo']): return "🚲"
        if any(x in n for x in ['samakat','skate']): return "🛴"
        if any(x in n for x in ["o'yinchoq","o'yin",'toy']): return "🧸"
        if any(x in n for x in ['yulka','stulchik','stul']): return "🪑"
        if any(x in n for x in ['kalyaska','aracha']): return "🍼"
        if any(x in n for x in ['mashinka','elektron','elektr']): return "🚗"
        if any(x in n for x in ['rolik','sket','sport','myach']): return "⛸️"
        return "📦"

    builder = InlineKeyboardBuilder()
    for cat in categories:
        size_icon = " 📏" if cat['has_sizes'] else ""
        emoji = cat_emoji(cat['name'])
        builder.button(
            text=f"{emoji} {cat['name']}{size_icon}",
            callback_data=f"cat_{cat['id']}"
        )
    builder.adjust(2)
    builder.button(text="🔍 Qidirish", callback_data="search_product")
    builder.adjust(2, 1)

    text = (
        "🏪 <b>BUYUK KIDS</b>\n"
        "━━━━━━━━━━━━━━━\n"
        "📂 Kategoriyani tanlang:\n"
        "<i>Mahsulot topish uchun qidiruvdan foydalaning</i>"
    )
    await message.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await state.set_state(OrderStates.choosing_category)

@dp.callback_query(F.data.regexp(r"^cat_\d+$"))
async def show_products(callback: types.CallbackQuery, state: FSMContext):
    cat_id   = int(callback.data.split("_")[1])
    products = db.get_products_by_category(cat_id)
    cat      = db.get_category(cat_id)
    if not products:
        await callback.answer("Bu kategoriyada mahsulot yo'q!", show_alert=True)
        return
    size_note = " (📏 razmer tanlanadi)" if cat['has_sizes'] else ""
    await callback.message.edit_text(f"📁 <b>{cat['name']}</b>{size_note}\n<i>Jami {len(products)} ta mahsulot</i>\n\nMahsulotni tanlang:", parse_mode="HTML")
    for product in products:
        price_line = f"💰 <b>{product['price']:,} so'm</b>"
        text = f"{'─'*20}\n🏷️ <b>{product['name']}</b>\n{price_line}\n"
        if product['description']:
            text += f"📝 <i>{product['description']}</i>\n"
        if product.get('sizes'):
            text += f"📏 <b>{' · '.join(product['sizes'].split(','))}</b>\n"
        builder = InlineKeyboardBuilder()
        builder.button(text="🛒 Savatga qo'shish", callback_data=f"add_{product['id']}")
        if product['photo_id']:
            await callback.message.answer_photo(photo=product['photo_id'], caption=text, reply_markup=builder.as_markup(), parse_mode="HTML")
        else:
            await callback.message.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    builder_back = InlineKeyboardBuilder()
    builder_back.button(text="🔍 Qidirish",      callback_data="search_product")
    builder_back.button(text="🔙 Kategoriyalar", callback_data="back_to_cats")
    builder_back.adjust(2)
    await callback.message.answer("⬆️ Yuqoridagi mahsulotlar", reply_markup=builder_back.as_markup())
    await state.set_state(OrderStates.choosing_product)

@dp.callback_query(F.data == "back_to_cats")
async def back_to_categories(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.delete()
    await show_catalog(callback.message, state)

@dp.callback_query(F.data == "search_product")
async def search_product_start(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer(
        "🔍 <b>Qidirish</b>\n\nMahsulot nomini yozing:",
        reply_markup=ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="❌ Bekor qilish")]], resize_keyboard=True),
        parse_mode="HTML"
    )
    await state.set_state(OrderStates.searching_product)
    await callback.answer()

@dp.message(OrderStates.searching_product, F.text)
async def do_search_product(message: types.Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("Bekor qilindi.", reply_markup=main_menu_keyboard(message.from_user.id))
        return
    query = message.text.strip()
    if len(query) < 2:
        await message.answer("❗ Kamida 2 ta harf kiriting.")
        return
    results = db.search_products(query)
    if not results:
        builder = InlineKeyboardBuilder()
        builder.button(text="🔍 Qayta qidirish",    callback_data="search_product")
        builder.button(text="📂 Katalogga qaytish", callback_data="back_to_cats")
        builder.adjust(1)
        await message.answer(f"😔 <b>«{query}»</b> bo'yicha hech narsa topilmadi.", reply_markup=builder.as_markup(), parse_mode="HTML")
        await state.clear()
        return
    await message.answer(f"🔍 <b>«{query}»</b> bo'yicha {len(results)} ta natija:", reply_markup=main_menu_keyboard(message.from_user.id), parse_mode="HTML")
    for product in results:
        text = f"🏷️ <b>{product['name']}</b>\n📁 {product.get('cat_name','')}\n💰 <b>{product['price']:,} so'm</b>\n"
        if product.get('description'):
            text += f"📝 <i>{product['description']}</i>\n"
        if product.get('sizes'):
            text += f"📏 <b>{' · '.join(product['sizes'].split(','))}</b>\n"
        builder = InlineKeyboardBuilder()
        builder.button(text="🛒 Savatga qo'shish", callback_data=f"add_{product['id']}")
        if product.get('photo_id'):
            await message.answer_photo(photo=product['photo_id'], caption=text, reply_markup=builder.as_markup(), parse_mode="HTML")
        else:
            await message.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await state.set_state(OrderStates.choosing_product)

@dp.callback_query(F.data.startswith("add_"))
async def ask_size_or_add(callback: types.CallbackQuery, state: FSMContext):
    product_id = int(callback.data.split("_")[1])
    product    = db.get_product(product_id)
    if product and product.get('sizes'):
        sizes_list = product['sizes'].split(",")
        builder = InlineKeyboardBuilder()
        for sz in sizes_list:
            builder.button(text=sz.strip(), callback_data=f"size_{product_id}_{sz.strip()}")
        builder.button(text="❌ Bekor", callback_data="size_cancel")
        builder.adjust(4)
        await callback.message.answer(f"📏 <b>{product['name']}</b>\n\nRazmerni tanlang:", reply_markup=builder.as_markup(), parse_mode="HTML")
        await state.set_state(OrderStates.choosing_size)
    else:
        db.add_to_cart(callback.from_user.id, product_id, size=None)
        await callback.answer(f"✅ {product['name']} savatga qo'shildi!")
        await callback.message.answer("✅ Savatga qo'shildi!", reply_markup=main_menu_keyboard(callback.from_user.id))

@dp.callback_query(F.data == "size_cancel")
async def size_cancel(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.delete()
    await state.set_state(OrderStates.choosing_product)

@dp.callback_query(F.data.startswith("size_"), OrderStates.choosing_size)
async def confirm_size(callback: types.CallbackQuery, state: FSMContext):
    parts      = callback.data.split("_")
    product_id = int(parts[1])
    size       = parts[2]
    db.add_to_cart(callback.from_user.id, product_id, size)
    product = db.get_product(product_id)
    await callback.answer(f"✅ {product['name']} ({size}) savatga qo'shildi!")
    await callback.message.delete()
    await callback.message.answer(f"✅ <b>{product['name']}</b> [{size}] savatga qo'shildi!", reply_markup=main_menu_keyboard(callback.from_user.id), parse_mode="HTML")
    await state.set_state(OrderStates.choosing_product)

# ══════════════════════════════════════
# SAVAT
# ══════════════════════════════════════
@dp.message(F.text.startswith("🛒 Savat"))
async def show_cart(message: types.Message, state: FSMContext):
    user_id    = message.from_user.id
    cart_items = db.get_cart(user_id)
    if not cart_items:
        await message.answer("🛒 Savatingiz bo'sh.")
        return
    text  = "🛒 <b>Savatingiz:</b>\n\n"
    total = 0
    builder = InlineKeyboardBuilder()
    for item in cart_items:
        subtotal    = item['price'] * item['quantity']
        total      += subtotal
        size_label  = f" [{item['size']}]" if item.get('size') else ""
        text += f"▫️ <b>{item['name']}</b>{size_label}\n   {item['quantity']} × {item['price']:,} = <b>{subtotal:,} so'm</b>\n"
        builder.button(text=f"❌ {item['name'][:15]}{size_label}", callback_data=f"rmv_{item['cart_id']}")
    discount_amt, final_price, pct = calc_discount(total)
    text += f"\n💰 Jami: <b>{total:,} so'm</b>"
    if discount_amt > 0:
        text += f"\n🎁 Chegirma ({pct}%): <b>-{discount_amt:,} so'm</b>\n✅ To'lov: <b>{final_price:,} so'm</b>"
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

# ══════════════════════════════════════
# CHECKOUT
# ══════════════════════════════════════
@dp.callback_query(F.data == "checkout")
async def checkout_start(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("📝 Ismingizni kiriting:", reply_markup=cancel_keyboard())
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
            keyboard=[[KeyboardButton(text="📱 Raqamni yuborish", request_contact=True)], [KeyboardButton(text="❌ Bekor qilish")]],
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
        "📍 <b>Manzilingizni kiriting:</b>",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="📌 Joylashuvimni yuborish", request_location=True)], [KeyboardButton(text="❌ Bekor qilish")]],
            resize_keyboard=True
        ),
        parse_mode="HTML"
    )
    await state.set_state(OrderStates.entering_address)

@dp.message(OrderStates.entering_address, F.location)
async def get_address_location(message: types.Message, state: FSMContext):
    lat = message.location.latitude
    lon = message.location.longitude
    import urllib.request, json as json_lib
    try:
        url = f"https://nominatim.openstreetmap.org/reverse?lat={lat}&lon={lon}&format=json&accept-language=uz"
        req = urllib.request.Request(url, headers={"User-Agent": "TelegramShopBot/1.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json_lib.loads(resp.read())
        address_parts = data.get("address", {})
        road    = address_parts.get("road", "")
        suburb  = address_parts.get("suburb", address_parts.get("neighbourhood", ""))
        city    = address_parts.get("city", address_parts.get("town", "Samarkand"))
        parts   = [p for p in [city, suburb, road] if p]
        address_text = ", ".join(parts) if parts else data.get("display_name", f"{lat:.5f}, {lon:.5f}")
    except Exception:
        address_text = f"📌 Geolokatsiya: {lat:.5f}, {lon:.5f}"
    await state.update_data(address=address_text, location_lat=lat, location_lon=lon)
    await message.answer(
        f"✅ Manzil: <b>{address_text}</b>\n\n🚚 <b>Dastavka turini tanlang:</b>",
        reply_markup=delivery_keyboard(),
        parse_mode="HTML"
    )
    await state.set_state(OrderStates.choosing_delivery)

@dp.message(OrderStates.entering_address, F.text)
async def get_address(message: types.Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("❌ Bekor qilindi.", reply_markup=main_menu_keyboard(message.from_user.id))
        return
    await state.update_data(address=message.text)
    await message.answer("🚚 <b>Dastavka turini tanlang:</b>", reply_markup=delivery_keyboard(), parse_mode="HTML")
    await state.set_state(OrderStates.choosing_delivery)

@dp.callback_query(F.data.startswith("delivery_"), OrderStates.choosing_delivery)
async def choose_delivery(callback: types.CallbackQuery, state: FSMContext):
    delivery_key   = callback.data.replace("delivery_", "")
    delivery_label = DELIVERY_TYPES.get(delivery_key, delivery_key)
    await state.update_data(delivery=delivery_label)
    builder = InlineKeyboardBuilder()
    builder.button(text="💵 Naqd",   callback_data="pay_cash")
    builder.button(text="💳 Payme",  callback_data="pay_payme")
    builder.button(text="💳 Click",  callback_data="pay_click")
    builder.adjust(1)
    await callback.message.edit_text(
        f"✅ Dastavka: <b>{delivery_label}</b>\n\n💳 To'lov usulini tanlang:",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )
    await state.set_state(OrderStates.choosing_payment)

@dp.callback_query(F.data.startswith("pay_"), OrderStates.choosing_payment)
async def process_payment(callback: types.CallbackQuery, state: FSMContext):
    payment_map = {"pay_cash": "💵 Naqd", "pay_payme": "💳 Payme", "pay_click": "💳 Click"}
    payment     = payment_map.get(callback.data, "Noma'lum")
    data        = await state.get_data()
    user_id     = callback.from_user.id
    cart_items  = db.get_cart(user_id)
    delivery    = data.get('delivery', '—')
    if not cart_items:
        await callback.answer("Savat bo'sh!", show_alert=True)
        await state.clear()
        return
    gross                        = sum(item['price'] * item['quantity'] for item in cart_items)
    discount_amt, final_price, pct = calc_discount(gross)
    order_id = db.create_order(
        user_id=user_id, customer_name=data['customer_name'],
        phone=data['phone'], address=data['address'],
        payment=payment, items=cart_items,
        total=final_price, discount_pct=pct, discount_amt=discount_amt
    )
    disc_line = f"\n💰 Asl narx: {gross:,} so'm\n🎁 Chegirma ({pct}%): -{discount_amt:,} so'm\n✅ To'lov: <b>{final_price:,} so'm</b>" if discount_amt > 0 else f"\n💰 Jami: <b>{gross:,} so'm</b>"
    confirm_text = (
        f"✅ <b>Buyurtmangiz qabul qilindi!</b>\n\n"
        f"🔢 Buyurtma №{order_id}\n"
        f"👤 {data['customer_name']}\n"
        f"📞 {data['phone']}\n"
        f"📍 {data['address']}\n"
        f"🚚 {delivery}\n"
        f"💳 {payment}"
        f"{disc_line}\n\n"
        f"📦 Tez orada siz bilan bog'lanamiz!"
    )
    await callback.message.answer(confirm_text, reply_markup=main_menu_keyboard(user_id), parse_mode="HTML")

    items_text = "\n".join([
        f"  • {item['name']}{' ['+item['size']+']' if item.get('size') else ''} ×{item['quantity']} = {item['price']*item['quantity']:,} so'm"
        for item in cart_items
    ])
    disc_admin = f"\n🎁 Chegirma ({pct}%): -{discount_amt:,} so'm" if discount_amt > 0 else ""

    # Geolokatsiya
    geo_line = ""
    if data.get('location_lat') and data.get('location_lon'):
        lat = data['location_lat']
        lon = data['location_lon']
        geo_line = f"\n📡 {lat:.5f}, {lon:.5f}\n🗺️ https://www.google.com/maps?q={lat},{lon}"

    admin_text = (
        f"🆕 <b>YANGI BUYURTMA №{order_id}</b>\n\n"
        f"👤 {data['customer_name']}\n"
        f"📞 {data['phone']}\n"
        f"📍 {data['address']}"
        f"{geo_line}\n"
        f"🚚 <b>{delivery}</b>\n"
        f"💳 {payment}\n\n"
        f"🛒 Mahsulotlar:\n{items_text}\n\n"
        f"💰 Asl narx: {gross:,} so'm"
        f"{disc_admin}\n"
        f"✅ <b>To'lov: {final_price:,} so'm</b>\n"
        f"🆔 TG ID: {user_id}"
    )
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Qabul qilindi", callback_data=f"order_accept_{order_id}")
    builder.button(text="❌ Bekor qilish",  callback_data=f"order_cancel_{order_id}")
    builder.adjust(2)
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, admin_text, reply_markup=builder.as_markup(), parse_mode="HTML")
        except Exception as e:
            logger.error(f"Admin xabar xatosi: {e}")

    workers        = db.get_workers()
    worker_builder = InlineKeyboardBuilder()
    worker_builder.button(text="✅ Qabul",    callback_data=f"worder_accept_{order_id}")
    worker_builder.button(text="🚚 Yetkazildi", callback_data=f"worder_deliver_{order_id}")
    worker_builder.button(text="❌ Bekor",     callback_data=f"worder_cancel_{order_id}")
    worker_builder.adjust(2)
    for worker in workers:
        try:
            await bot.send_message(worker['telegram_id'], admin_text, reply_markup=worker_builder.as_markup(), parse_mode="HTML")
        except Exception as e:
            logger.error(f"Ishchi xabar xatosi: {e}")

    db.clear_cart(user_id)
    await state.clear()

# ══════════════════════════════════════
# ORDER STATUS
# ══════════════════════════════════════
@dp.callback_query(F.data.startswith("order_accept_"))
async def order_accept(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id): return
    order_id = int(callback.data.split("_")[2])
    db.update_order_status(order_id, "accepted")
    order = db.get_order(order_id)
    if order:
        try: await bot.send_message(order['user_id'], f"✅ Buyurtma №{order_id} qabul qilindi! Rahmat 🙏")
        except: pass
    await callback.message.edit_text(callback.message.text + "\n\n✅ QABUL QILINDI", parse_mode="HTML")

@dp.callback_query(F.data.startswith("order_cancel_"))
async def order_cancel(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id): return
    order_id = int(callback.data.split("_")[2])
    db.update_order_status(order_id, "cancelled")
    order = db.get_order(order_id)
    if order:
        try: await bot.send_message(order['user_id'], f"❌ Buyurtma №{order_id} bekor qilindi.")
        except: pass
    await callback.message.edit_text(callback.message.text + "\n\n❌ BEKOR QILINDI", parse_mode="HTML")

@dp.callback_query(F.data.startswith("worder_accept_"))
async def worker_order_accept(callback: types.CallbackQuery):
    if not is_worker(callback.from_user.id): return
    order_id = int(callback.data.split("_")[2])
    db.update_order_status(order_id, "accepted")
    order = db.get_order(order_id)
    if order:
        try: await bot.send_message(order['user_id'], f"✅ Buyurtma №{order_id} qabul qilindi! Rahmat 🙏")
        except: pass
    await callback.message.edit_text(callback.message.text + "\n\n✅ QABUL QILINDI", parse_mode="HTML")
    await callback.answer("✅ Qabul qilindi!")

@dp.callback_query(F.data.startswith("worder_deliver_"))
async def worker_order_deliver(callback: types.CallbackQuery):
    if not is_worker(callback.from_user.id): return
    order_id = int(callback.data.split("_")[2])
    db.update_order_status(order_id, "delivered")
    order = db.get_order(order_id)
    if order:
        try: await bot.send_message(order['user_id'], f"🚚 Buyurtma №{order_id} yetkazib berildi! Rahmat 🙏")
        except: pass
    await callback.message.edit_text(callback.message.text + "\n\n🚚 YETKAZILDI", parse_mode="HTML")
    await callback.answer("🚚 Yetkazildi!")

@dp.callback_query(F.data.startswith("worder_cancel_"))
async def worker_order_cancel(callback: types.CallbackQuery):
    if not is_worker(callback.from_user.id): return
    order_id = int(callback.data.split("_")[2])
    db.update_order_status(order_id, "cancelled")
    order = db.get_order(order_id)
    if order:
        try: await bot.send_message(order['user_id'], f"❌ Buyurtma №{order_id} bekor qilindi.")
        except: pass
    await callback.message.edit_text(callback.message.text + "\n\n❌ BEKOR QILINDI", parse_mode="HTML")
    await callback.answer("❌ Bekor qilindi!")

# ══════════════════════════════════════
# MY ORDERS
# ══════════════════════════════════════
@dp.message(F.text == "📦 Buyurtmalarim")
async def my_orders(message: types.Message):
    orders = db.get_user_orders(message.from_user.id)
    if not orders:
        await message.answer("📦 Sizda hali buyurtma yo'q.")
        return
    status_emoji = {"pending": "⏳", "accepted": "✅", "cancelled": "❌", "delivered": "🚚"}
    text = "📦 <b>Buyurtmalaringiz:</b>\n\n"
    for order in orders[-10:]:
        emoji    = status_emoji.get(order['status'], "❓")
        disc_line = f" (chegirma -{order['discount_amt']:,})" if order.get('discount_amt') else ""
        text += f"{emoji} <b>№{order['id']}</b> — {order['total']:,} so'm{disc_line}\n📅 {order['created_at'][:10]}\n\n"
    await message.answer(text, parse_mode="HTML")

@dp.message(F.text == "📞 Aloqa")
async def contact(message: types.Message):
    await message.answer("📞 <b>Biz bilan bog'laning:</b>\n\n📱 Tel: +998 99 7420160\n📱 Telegram: @Buyukkids1\n🕐 Ish vaqti: 9:00 - 21:00", parse_mode="HTML")

# ══════════════════════════════════════
# ADMIN / WORKER PANELS
# ══════════════════════════════════════
@dp.message(F.text == "👨‍💼 Ishchi panel")
async def worker_panel(message: types.Message, state: FSMContext):
    if not is_worker(message.from_user.id):
        await message.answer("❌ Ruxsat yo'q!")
        return
    await state.clear()
    await message.answer("👨‍💼 <b>Ishchi panel</b>", reply_markup=worker_menu_keyboard(), parse_mode="HTML")

@dp.message(F.text == "👑 Admin panel")
async def admin_panel(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("❌ Ruxsat yo'q!")
        return
    await state.clear()
    await message.answer("👑 <b>Admin panel</b>", reply_markup=admin_menu_keyboard(), parse_mode="HTML")

@dp.message(F.text == "🔙 Orqaga")
async def back_to_main(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("Bosh menyu:", reply_markup=main_menu_keyboard(message.from_user.id))

# ══════════════════════════════════════
# HISOBOTLAR
# ══════════════════════════════════════
@dp.message(F.text == "📈 Hisobotlar")
async def reports_menu(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.clear()
    builder = ReplyKeyboardBuilder()
    builder.button(text="📅 Oylik hisobot")
    builder.button(text="📆 Davr hisoboti")
    builder.button(text="🚚 Dastavka hisoboti")
    builder.button(text="🔙 Orqaga")
    builder.adjust(2)
    await message.answer("📈 <b>Hisobotlar</b>\nQaysi hisobotni ko'rmoqchisiz?", reply_markup=builder.as_markup(), parse_mode="HTML")

@dp.message(F.text == "📅 Oylik hisobot")
async def monthly_report(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    from datetime import datetime
    now         = datetime.now()
    month_start = now.strftime("%Y-%m-01")
    with db.get_connection() as conn:
        orders = conn.execute(
            "SELECT * FROM orders WHERE created_at >= ? ORDER BY created_at DESC",
            (month_start,)
        ).fetchall()
    if not orders:
        await message.answer("📭 Bu oyda buyurtma yo'q.")
        return
    total_orders   = len(orders)
    total_revenue  = sum(o['total'] for o in orders)
    total_discount = sum(o['discount_amt'] for o in orders if o['discount_amt'])
    pending   = sum(1 for o in orders if o['status'] == 'pending')
    accepted  = sum(1 for o in orders if o['status'] == 'accepted')
    delivered = sum(1 for o in orders if o['status'] == 'delivered')
    cancelled = sum(1 for o in orders if o['status'] == 'cancelled')
    text = (
        f"📅 <b>{now.strftime('%Y — %B')} oylik hisobot</b>\n\n"
        f"📦 Jami buyurtmalar: <b>{total_orders}</b>\n"
        f"⏳ Kutmoqda: {pending}\n"
        f"✅ Qabul qilindi: {accepted}\n"
        f"🚚 Yetkazildi: {delivered}\n"
        f"❌ Bekor qilindi: {cancelled}\n\n"
        f"💰 Jami tushum: <b>{total_revenue:,} so'm</b>\n"
        f"🎁 Chegirma berildi: <b>{total_discount:,} so'm</b>"
    )
    await message.answer(text, parse_mode="HTML")

@dp.message(F.text == "📆 Davr hisoboti")
async def period_report_start(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await message.answer("📆 Boshlanish sanasini kiriting:\nFormat: <code>2025-01-01</code>", reply_markup=cancel_keyboard(), parse_mode="HTML")
    await state.set_state(ReportStates.entering_date_from)

@dp.message(ReportStates.entering_date_from, F.text)
async def period_report_from(message: types.Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("Bekor qilindi.", reply_markup=admin_menu_keyboard())
        return
    await state.update_data(date_from=message.text.strip())
    await message.answer("📆 Tugash sanasini kiriting:\nFormat: <code>2025-12-31</code>", parse_mode="HTML")
    await state.set_state(ReportStates.entering_date_to)

@dp.message(ReportStates.entering_date_to, F.text)
async def period_report_to(message: types.Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("Bekor qilindi.", reply_markup=admin_menu_keyboard())
        return
    data      = await state.get_data()
    date_from = data['date_from']
    date_to   = message.text.strip() + " 23:59:59"
    with db.get_connection() as conn:
        orders = conn.execute(
            "SELECT * FROM orders WHERE created_at BETWEEN ? AND ? ORDER BY created_at DESC",
            (date_from, date_to)
        ).fetchall()
    await state.clear()
    if not orders:
        await message.answer(f"📭 {date_from} — {date_to[:10]} orasida buyurtma yo'q.", reply_markup=admin_menu_keyboard())
        return
    total_orders   = len(orders)
    total_revenue  = sum(o['total'] for o in orders)
    total_discount = sum(o['discount_amt'] for o in orders if o['discount_amt'])
    delivered = sum(1 for o in orders if o['status'] == 'delivered')
    cancelled = sum(1 for o in orders if o['status'] == 'cancelled')
    text = (
        f"📆 <b>{date_from} — {date_to[:10]}</b>\n\n"
        f"📦 Jami buyurtmalar: <b>{total_orders}</b>\n"
        f"🚚 Yetkazildi: {delivered}\n"
        f"❌ Bekor: {cancelled}\n\n"
        f"💰 Jami tushum: <b>{total_revenue:,} so'm</b>\n"
        f"🎁 Chegirmalar: <b>{total_discount:,} so'm</b>"
    )
    await message.answer(text, reply_markup=admin_menu_keyboard(), parse_mode="HTML")

@dp.message(F.text == "🚚 Dastavka hisoboti")
async def delivery_report(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    with db.get_connection() as conn:
        delivered = conn.execute(
            "SELECT * FROM orders WHERE status='delivered' ORDER BY created_at DESC LIMIT 50"
        ).fetchall()
        pending = conn.execute(
            "SELECT * FROM orders WHERE status IN ('pending','accepted') ORDER BY created_at DESC LIMIT 50"
        ).fetchall()

    # Yetkazilganlar
    text = "🚚 <b>DASTAVKA HISOBOTI</b>\n\n"

    text += f"✅ <b>Yetkazildi: {len(delivered)} ta</b>\n"
    if delivered:
        total_d = sum(o['total'] for o in delivered)
        text += f"💰 Jami: {total_d:,} so'm\n\n"
        for o in delivered[:15]:
            text += f"  ✅ №{o['id']} | {o['customer_name']} | {o['total']:,} so'm | {o['created_at'][:10]}\n"
        if len(delivered) > 15:
            text += f"  ...va yana {len(delivered)-15} ta\n"
    else:
        text += "  Hozircha yo'q\n"

    text += f"\n⏳ <b>Kutmoqda / Jarayonda: {len(pending)} ta</b>\n"
    if pending:
        total_p = sum(o['total'] for o in pending)
        text += f"💰 Jami: {total_p:,} so'm\n\n"
        status_map = {"pending": "⏳", "accepted": "🔄"}
        for o in pending[:15]:
            emoji = status_map.get(o['status'], "❓")
            text += f"  {emoji} №{o['id']} | {o['customer_name']} | {o['total']:,} so'm | {o['created_at'][:10]}\n"
        if len(pending) > 15:
            text += f"  ...va yana {len(pending)-15} ta\n"
    else:
        text += "  Hozircha yo'q\n"

    await message.answer(text, parse_mode="HTML")

# ══════════════════════════════════════
# MAHSULOT QO'SHISH / TAHRIRLASH
# ══════════════════════════════════════
@dp.message(F.text == "➕ Kategoriya qo'shish")
async def add_category_start(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    await message.answer("📁 Kategoriya nomini kiriting:", reply_markup=cancel_keyboard())
    await state.set_state(AdminStates.adding_category_name)

@dp.message(AdminStates.adding_category_name, F.text)
async def get_category_name(message: types.Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("Bekor qilindi.", reply_markup=admin_menu_keyboard())
        return
    await state.update_data(cat_name=message.text)
    builder = InlineKeyboardBuilder()
    builder.button(text="📏 Ha, razmer kerak",      callback_data="cat_sizes_yes")
    builder.button(text="🚫 Yo'q, razmer shart emas", callback_data="cat_sizes_no")
    builder.adjust(1)
    await message.answer(f"📁 <b>{message.text}</b>\n\nBu kategoriyada razmer so'rash kerakmi?", reply_markup=builder.as_markup(), parse_mode="HTML")
    await state.set_state(AdminStates.adding_category_sizes)

@dp.callback_query(F.data.in_({"cat_sizes_yes", "cat_sizes_no"}), AdminStates.adding_category_sizes)
async def save_category(callback: types.CallbackQuery, state: FSMContext):
    data      = await state.get_data()
    has_sizes = callback.data == "cat_sizes_yes"
    db.add_category(data['cat_name'], has_sizes)
    await callback.message.edit_text(f"✅ '{data['cat_name']}' kategoriyasi qo'shildi!")
    await callback.message.answer("Davom etamiz:", reply_markup=admin_menu_keyboard())
    await state.clear()

@dp.message(F.text == "➕ Mahsulot qo'shish")
async def add_product_start(message: types.Message, state: FSMContext):
    if not is_worker(message.from_user.id): return
    categories = db.get_categories()
    if not categories:
        await message.answer("❗ Avval kategoriya qo'shing!")
        return
    builder = InlineKeyboardBuilder()
    for cat in categories:
        size_icon = " 📏" if cat['has_sizes'] else ""
        builder.button(text=f"{cat['name']}{size_icon}", callback_data=f"admin_cat_{cat['id']}")
    builder.adjust(2)
    await message.answer("📁 Mahsulot uchun kategoriyani tanlang:", reply_markup=builder.as_markup())
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
    product_name = message.text.strip()
    if db.product_name_exists(product_name):
        builder = InlineKeyboardBuilder()
        builder.button(text="✅ Baribir qo'shish", callback_data=f"force_add_name:{product_name}")
        builder.button(text="❌ Boshqa nom berish", callback_data="retry_product_name")
        builder.adjust(1)
        await message.answer(f"⚠️ <b>«{product_name}»</b> nomli mahsulot allaqachon mavjud!", reply_markup=builder.as_markup(), parse_mode="HTML")
        return
    await state.update_data(product_name=product_name)
    await message.answer("💰 Narxini kiriting (faqat raqam):")
    await state.set_state(AdminStates.adding_product_price)

@dp.callback_query(F.data == "retry_product_name", AdminStates.adding_product_name)
async def retry_product_name(callback: types.CallbackQuery):
    await callback.message.edit_text("🏷️ Boshqa nom kiriting:")

@dp.callback_query(F.data.startswith("force_add_name:"))
async def force_add_name(callback: types.CallbackQuery, state: FSMContext):
    product_name = callback.data.split(":", 1)[1]
    await state.update_data(product_name=product_name)
    await callback.message.edit_text(f"✅ <b>«{product_name}»</b> nomi tasdiqlandi.", parse_mode="HTML")
    await callback.message.answer("💰 Narxini kiriting:")
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
        await message.answer("❗ Faqat raqam kiriting!")
        return
    await state.update_data(product_price=price)
    await message.answer("📝 Tavsif kiriting (yoki /skip):")
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
    data = await state.get_data()
    cat  = db.get_category(data['category_id'])
    if cat and cat['has_sizes']:
        await message.answer("📏 Razmerlarni kiriting (vergul bilan):\nMasalan: <code>86, 92, 98, 104</code>\n\nYoki /skip", reply_markup=cancel_keyboard(), parse_mode="HTML")
        await state.set_state(AdminStates.adding_product_sizes)
    else:
        await message.answer("📸 Rasmini yuboring (yoki /skip):", reply_markup=cancel_keyboard())
        await state.set_state(AdminStates.adding_product_photo)

@dp.message(AdminStates.adding_product_sizes, F.text)
async def get_product_sizes(message: types.Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        menu = admin_menu_keyboard() if is_admin(message.from_user.id) else worker_menu_keyboard()
        await message.answer("Bekor qilindi.", reply_markup=menu)
        return
    sizes_str = None if message.text == "/skip" else ",".join([s.strip() for s in message.text.replace(" ", "").split(",") if s.strip()])
    await state.update_data(product_sizes=sizes_str)
    await message.answer("📸 Rasmini yuboring (yoki /skip):", reply_markup=cancel_keyboard())
    await state.set_state(AdminStates.adding_product_photo)

@dp.message(AdminStates.adding_product_photo)
async def get_product_photo(message: types.Message, state: FSMContext):
    if message.text and message.text == "❌ Bekor qilish":
        await state.clear()
        menu = admin_menu_keyboard() if is_admin(message.from_user.id) else worker_menu_keyboard()
        await message.answer("Bekor qilindi.", reply_markup=menu)
        return
    photo_id  = None
    photo_url = None
    if message.photo:
        photo_id  = message.photo[-1].file_id
        photo_url = await save_photo_locally(photo_id)
    data = await state.get_data()
    db.add_product(
        name=data['product_name'], price=data['product_price'],
        description=data['product_description'], category_id=data['category_id'],
        photo_id=photo_id, photo_url=photo_url, sizes=data.get('product_sizes')
    )
    menu = admin_menu_keyboard() if is_admin(message.from_user.id) else worker_menu_keyboard()
    await message.answer(f"✅ '<b>{data['product_name']}</b>' qo'shildi!\n💰 {data['product_price']:,} so'm", reply_markup=menu, parse_mode="HTML")
    await state.clear()

@dp.message(F.text == "✏️ Mahsulot tahrirlash")
async def edit_product_start(message: types.Message, state: FSMContext):
    if not is_worker(message.from_user.id): return
    products = db.get_all_products()
    if not products:
        await message.answer("Mahsulotlar yo'q.")
        return
    await message.answer(
        "🔍 <b>Mahsulot qidirish</b>\n\nNomini yozing (yoki bir qismini):",
        reply_markup=cancel_keyboard(),
        parse_mode="HTML"
    )
    await state.set_state(AdminStates.editing_product_select)

@dp.message(AdminStates.editing_product_select, F.text)
async def edit_product_search(message: types.Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        menu = admin_menu_keyboard() if is_admin(message.from_user.id) else worker_menu_keyboard()
        await message.answer("Bekor qilindi.", reply_markup=menu)
        return
    query = message.text.strip()
    results = db.search_products(query) if len(query) >= 1 else db.get_all_products()
    if not results:
        await message.answer(f"😔 <b>«{query}»</b> bo'yicha mahsulot topilmadi.\nQayta yozing:", parse_mode="HTML")
        return
    builder = InlineKeyboardBuilder()
    for p in results[:20]:
        builder.button(text=f"✏️ {p['name']} ({p['price']:,})", callback_data=f"edit_prod_{p['id']}")
    builder.adjust(1)
    await message.answer(
        f"🔍 <b>{len(results)} ta topildi</b>. Tanlang:",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )

@dp.callback_query(F.data.startswith("edit_prod_"), AdminStates.editing_product_select)
async def edit_product_select(callback: types.CallbackQuery, state: FSMContext):
    product_id = int(callback.data.split("_")[2])
    product    = db.get_product(product_id)
    await state.update_data(edit_product_id=product_id)
    builder = InlineKeyboardBuilder()
    builder.button(text="🏷️ Nomini o'zgartirish",   callback_data="edit_field_name")
    builder.button(text="💰 Narxini o'zgartirish",  callback_data="edit_field_price")
    builder.button(text="📝 Tavsifini o'zgartirish", callback_data="edit_field_description")
    builder.button(text="📸 Rasmini o'zgartirish",  callback_data="edit_field_photo")
    builder.button(text="❌ Bekor",                  callback_data="edit_cancel")
    builder.adjust(2)
    text = f"✏️ <b>{product['name']}</b>\n💰 {product['price']:,} so'm\n\nNimani o'zgartirmoqchisiz?"
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
        await callback.message.answer("📸 Yangi rasmni yuboring:", reply_markup=cancel_keyboard())
        await state.set_state(AdminStates.editing_product_photo_new)
    else:
        prompts = {"name": "🏷️ Yangi nomini kiriting:", "price": "💰 Yangi narxini kiriting:", "description": "📝 Yangi tavsifini kiriting (yoki /skip):"}
        await callback.message.answer(prompts[field], reply_markup=cancel_keyboard())
        await state.set_state(AdminStates.editing_product_value)

@dp.message(AdminStates.editing_product_value, F.text)
async def edit_product_value(message: types.Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        menu = admin_menu_keyboard() if is_admin(message.from_user.id) else worker_menu_keyboard()
        await message.answer("Bekor qilindi.", reply_markup=menu)
        return
    data    = await state.get_data()
    field   = data['edit_field']
    if field == "price":
        try: value = int(message.text.replace(" ", "").replace(",", ""))
        except ValueError:
            await message.answer("❗ Faqat raqam kiriting!")
            return
    elif field == "description" and message.text == "/skip":
        value = ""
    else:
        value = message.text
    db.update_product_field(data['edit_product_id'], field, value)
    menu = admin_menu_keyboard() if is_admin(message.from_user.id) else worker_menu_keyboard()
    await message.answer("✅ Mahsulot yangilandi!", reply_markup=menu)
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
    data      = await state.get_data()
    photo_id  = message.photo[-1].file_id
    photo_url = await save_photo_locally(photo_id)
    db.update_product_field(data['edit_product_id'], 'photo_id',  photo_id)
    db.update_product_field(data['edit_product_id'], 'photo_url', photo_url)
    menu = admin_menu_keyboard() if is_admin(message.from_user.id) else worker_menu_keyboard()
    await message.answer("✅ Rasm yangilandi!", reply_markup=menu)
    await state.clear()

@dp.message(F.text == "🗑️ Mahsulot o'chirish")
async def delete_product_start(message: types.Message, state: FSMContext):
    if not is_worker(message.from_user.id): return
    products = db.get_all_products()
    if not products:
        await message.answer("Mahsulotlar yo'q.")
        return
    await message.answer(
        "🔍 <b>O'chiriladigan mahsulotni qidiring:</b>\n\nNomini yozing:",
        reply_markup=cancel_keyboard(),
        parse_mode="HTML"
    )
    await state.set_state(AdminStates.deleting_product)

@dp.message(AdminStates.deleting_product, F.text)
async def delete_product_search(message: types.Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        menu = admin_menu_keyboard() if is_admin(message.from_user.id) else worker_menu_keyboard()
        await message.answer("Bekor qilindi.", reply_markup=menu)
        return
    query = message.text.strip()
    results = db.search_products(query) if len(query) >= 1 else db.get_all_products()
    if not results:
        await message.answer(f"😔 <b>«{query}»</b> topilmadi. Qayta yozing:", parse_mode="HTML")
        return
    builder = InlineKeyboardBuilder()
    for p in results[:20]:
        builder.button(text=f"❌ {p['name']} ({p['price']:,})", callback_data=f"del_prod_{p['id']}")
    builder.adjust(1)
    await message.answer(
        f"🔍 <b>{len(results)} ta topildi</b>. O'chiriladigani tanlang:",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )

@dp.callback_query(F.data.startswith("del_prod_"))
async def delete_product(callback: types.CallbackQuery):
    if not is_worker(callback.from_user.id): return
    product_id = int(callback.data.split("_")[2])
    product    = db.get_product(product_id)
    db.delete_product(product_id)
    await callback.message.edit_text(f"✅ '{product['name']}' o'chirildi!")

@dp.message(F.text == "🗑️ Kategoriya o'chirish")
async def delete_category_start(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
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
    if not is_admin(callback.from_user.id): return
    cat_id   = int(callback.data.split("_")[2])
    cat_name = db.get_category_name(cat_id)
    db.delete_category(cat_id)
    await callback.message.edit_text(f"✅ '{cat_name}' kategoriyasi o'chirildi!")

@dp.message(F.text == "📊 Buyurtmalar")
async def worker_orders(message: types.Message):
    if not is_worker(message.from_user.id): return
    orders = db.get_all_orders()
    if not orders:
        await message.answer("📭 Hozircha buyurtmalar yo'q.")
        return
    status_map = {"pending": "⏳ Kutmoqda", "accepted": "✅ Qabul", "delivered": "🚚 Yetkazildi", "cancelled": "❌ Bekor"}
    text    = "📊 <b>Oxirgi buyurtmalar:</b>\n\n"
    builder = InlineKeyboardBuilder()
    for order in orders[:20]:
        text += f"{status_map.get(order['status'],'❓')} <b>№{order['id']}</b> | {order['customer_name']} | {order['total']:,} so'm | {order['created_at'][:10]}\n"
        builder.button(text=f"№{order['id']} — batafsil", callback_data=f"worder_detail_{order['id']}")
    builder.adjust(1)
    await message.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")

@dp.callback_query(F.data.startswith("worder_detail_"))
async def worker_order_detail(callback: types.CallbackQuery):
    if not is_worker(callback.from_user.id): return
    order_id = int(callback.data.split("_")[2])
    order    = db.get_order(order_id)
    items    = db.get_order_items(order_id)
    if not order:
        await callback.answer("Buyurtma topilmadi!", show_alert=True)
        return
    status_map = {"pending": "⏳ Kutmoqda", "accepted": "✅ Qabul", "delivered": "🚚 Yetkazildi", "cancelled": "❌ Bekor"}
    items_text = "\n".join([f"  • {i['product_name']}{' ['+i['size']+']' if i.get('size') else ''} ×{i['quantity']} = {i['price']*i['quantity']:,} so'm" for i in items])
    disc_line  = f"\n🎁 Chegirma ({order['discount_pct']}%): -{order['discount_amt']:,} so'm" if order.get('discount_amt') else ""
    text = (
        f"📦 <b>Buyurtma №{order_id}</b>\n\n"
        f"👤 {order['customer_name']}\n📞 {order['phone']}\n📍 {order['address']}\n"
        f"💳 {order['payment']}\n📅 {order['created_at'][:16]}\n"
        f"📊 {status_map.get(order['status'],'❓')}\n\n"
        f"🛒 Mahsulotlar:\n{items_text}{disc_line}\n"
        f"✅ <b>Jami: {order['total']:,} so'm</b>"
    )
    builder = InlineKeyboardBuilder()
    if order['status'] == "pending":
        builder.button(text="✅ Qabul",    callback_data=f"worder_accept_{order_id}")
        builder.button(text="❌ Bekor",    callback_data=f"worder_cancel_{order_id}")
    if order['status'] == "accepted":
        builder.button(text="🚚 Yetkazildi", callback_data=f"worder_deliver_{order_id}")
        builder.button(text="❌ Bekor",      callback_data=f"worder_cancel_{order_id}")
    builder.adjust(2)
    await callback.message.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()

@dp.message(F.text == "📊 Barcha buyurtmalar")
async def all_orders(message: types.Message):
    if not is_admin(message.from_user.id): return
    orders = db.get_all_orders()
    if not orders:
        await message.answer("Buyurtmalar yo'q.")
        return
    status_emoji = {"pending": "⏳", "accepted": "✅", "cancelled": "❌", "delivered": "🚚"}
    text = "📊 <b>Oxirgi buyurtmalar:</b>\n\n"
    for order in orders[:20]:
        text += f"{status_emoji.get(order['status'],'❓')} №{order['id']} | {order['customer_name']} | {order['total']:,} so'm | {order['created_at'][:10]}\n"
    await message.answer(text, parse_mode="HTML")

@dp.message(F.text == "👨‍💼 Ishchilar boshqaruvi")
async def workers_management(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    await state.clear()
    workers   = db.get_workers()
    passwords = db.get_worker_passwords()
    text = "👨‍💼 <b>Ishchilar boshqaruvi</b>\n\n"
    if workers:
        text += "✅ <b>Faol ishchilar:</b>\n"
        for w in workers:
            uname = f"@{w['username']}" if w.get('username') else "—"
            text += f"  • {w['full_name']} ({uname})\n"
    else:
        text += "👤 Faol ishchilar yo'q\n"
    text += "\n🔑 <b>So'ngi parollar:</b>\n"
    for pw in passwords[:10]:
        status = f"✅ {pw['used_by_name']}" if pw['is_used'] else "⏳ Kutmoqda"
        text  += f"  <code>{pw['password']}</code> — {status}\n"
    builder = InlineKeyboardBuilder()
    builder.button(text="➕ Yangi parol yaratish", callback_data="create_worker_pwd")
    if workers:
        builder.button(text="🗑️ Ishchini o'chirish", callback_data="remove_worker_start")
    builder.adjust(1)
    await message.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")

@dp.callback_query(F.data == "create_worker_pwd")
async def create_worker_pwd(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id): return
    password = gen_password(8)
    db.create_worker_password(password, callback.from_user.id)
    await callback.answer()
    await callback.message.answer(f"✅ Yangi ishchi paroli:\n\n🔑 <code>{password}</code>\n\nBu parolni ishchiga yuboring. /worker komandasi orqali kiradi.\n⚠️ Parol faqat bir marta ishlatiladi!", parse_mode="HTML")

@dp.callback_query(F.data == "remove_worker_start")
async def remove_worker_start(callback: types.CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return
    workers = db.get_workers()
    if not workers:
        await callback.answer("Ishchilar yo'q!", show_alert=True)
        return
    builder = InlineKeyboardBuilder()
    for w in workers:
        builder.button(text=f"❌ {w['full_name']}", callback_data=f"fire_worker_{w['telegram_id']}")
    builder.adjust(1)
    await callback.message.answer("O'chiriladigan ishchini tanlang:", reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith("fire_worker_"))
async def fire_worker(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id): return
    worker_tid = int(callback.data.split("_")[2])
    worker     = db.get_user(worker_tid)
    db.remove_worker(worker_tid)
    name = worker['full_name'] if worker else str(worker_tid)
    await callback.message.edit_text(f"✅ {name} ishchilar ro'yxatidan chiqarildi.")
    try: await bot.send_message(worker_tid, "ℹ️ Sizning ishchi huquqlaringiz bekor qilindi.")
    except: pass

# ══════════════════════════════════════
# MAIN
# ══════════════════════════════════════
async def main():
    db.init_db()
    logger.info("Bot ishga tushmoqda...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

"""
BUYUK KIDS — Flask API
Veb-sahifa uchun kategoriya va mahsulotlarni beradi
"""
from flask import Flask, jsonify, request, send_file, send_from_directory
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from functools import wraps
from database import Database
import os
import secrets
import uuid

PHOTOS_DIR = os.path.join(os.path.dirname(__file__), "photos")
os.makedirs(PHOTOS_DIR, exist_ok=True)

ALLOWED_PHOTO_EXT = {"jpg", "jpeg", "png", "webp", "gif"}

app = Flask(__name__)
CORS(app)

DB_PATH = os.getenv("DB_PATH", "shop.db")
db = Database(DB_PATH)

db.init_db()

# Bosh sahifa matnlari uchun standart (default) qiymatlar.
# Admin panelda hali hech narsa saqlanmagan bo'lsa, shular ko'rsatiladi.
DEFAULT_CONTENT = {
    "hero_badge":     "🧸 Farzandlar uchun sevgi bilan",
    "hero_title":     "Farzandingiz uchun eng chiroyli va sifatli kiyimlar",
    "hero_subtitle":  "0 yoshdan 14 yoshgacha bolalar kiyimi, oyoq kiyimi va aksessuarlari — bir joydan, qulay va ishonchli",
    "hero_cta":       "Katalogni ko'rish",
    "trust1_icon": "9:00–21:00", "trust1_text": "Har kuni ish vaqti",
    "trust2_icon": "500+", "trust2_text": "Xilma-xil mahsulotlar",
    "trust3_icon": "1000+", "trust3_text": "Mamnun ota-onalar",
    "trust4_icon": "0–14", "trust4_text": "Yosh toifalari uchun",
    "about_title":    "Nega aynan BUYUK KIDS?",
    "about_text":     "Biz har bir farzand chiroyli va qulay kiyinishi kerak, deb bilamiz. Shuning uchun faqat sifatli, teri va shamollatuvchi matolardan tikilgan, chidamli hamda zamonaviy dizayndagi kiyimlarni tanlab taqdim etamiz.",
    "diff1_icon": "🌿", "diff1_title": "Sifatli matolar",
    "diff1_text": "Faqat bolalar terisiga zararsiz, nafas oladigan matolardan tikilgan kiyimlar",
    "diff2_icon": "⚡", "diff2_title": "Tezkor yetkazib berish",
    "diff2_text": "Buyurtmangiz eng qisqa muddatda, aynan ko'rsatgan manzilingizga yetkaziladi",
    "diff3_icon": "🤝", "diff3_title": "Ishonchli xizmat",
    "diff3_text": "Har bir savolingizga tezkor javob va do'stona muomala — sizni doim eshitamiz",
    "footer_about":   "BUYUK KIDS — farzandingiz uchun chiroyli va sifatli kiyimlar do'koni.",
    "contact_address": "Samarqand shahri",
    "contact_hours":    "Har kuni 9:00 – 21:00",
    "contact_phone":    "",
}

# Birinchi marta ishga tushganda — bootstrap admin (agar hech kim yo'q bo'lsa)
_boot_user = os.getenv("BOOTSTRAP_ADMIN_USER", "")
_boot_pass = os.getenv("BOOTSTRAP_ADMIN_PASS", "")
if _boot_user and _boot_pass and db.count_site_admins() == 0:
    db.create_site_admin(_boot_user, generate_password_hash(_boot_pass),
                          full_name="Bosh admin", role="admin")
    print(f"✅ Bootstrap admin yaratildi: {_boot_user}")


# ══════════════════════════════════════
# ADMIN AUTH HELPERS
# ══════════════════════════════════════
def require_auth(role=None):
    """Admin panel endpointlarini himoya qiluvchi dekorator.
    role='admin' bo'lsa faqat admin roli o'tadi, aks holda admin yoki worker."""
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            auth = request.headers.get("Authorization", "")
            token = auth.split(" ", 1)[1] if auth.startswith("Bearer ") else auth
            if not token:
                return jsonify({"ok": False, "error": "Avtorizatsiya talab qilinadi"}), 401
            admin = db.get_session_admin(token)
            if not admin:
                return jsonify({"ok": False, "error": "Sessiya yaroqsiz, qaytadan kiring"}), 401
            if role == "admin" and admin["role"] != "admin":
                return jsonify({"ok": False, "error": "Faqat admin uchun ruxsat"}), 403
            request.admin = admin
            return fn(*args, **kwargs)
        return wrapper
    return decorator

@app.route("/")
def index():
    return send_file("buyukkids_shop.html")

@app.route("/api/categories", methods=["GET"])
def get_categories():
    try:
        categories = db.get_categories()
        return jsonify({"ok": True, "result": categories})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/api/products/<int:cat_id>", methods=["GET"])
def get_products(cat_id):
    try:
        products = db.get_products_by_category(cat_id)
        result = []
        for p in products:
            result.append({
                "id":          p["id"],
                "name":        p["name"],
                "price":       p["price"],
                "description": p.get("description", ""),
                "sizes":       p.get("sizes", None),
                "photo_url":   p.get("photo_url", None)
            })
        return jsonify({"ok": True, "result": result})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/api/search", methods=["GET"])
def search():
    query = request.args.get("q", "").strip()
    if len(query) < 2:
        return jsonify({"ok": False, "error": "Kamida 2 harf"}), 400
    try:
        products = db.search_products(query)
        result = []
        for p in products:
            result.append({
                "id":          p["id"],
                "name":        p["name"],
                "price":       p["price"],
                "description": p.get("description", ""),
                "sizes":       p.get("sizes", None),
                "cat_name":    p.get("cat_name", ""),
                "photo_url":   p.get("photo_url", None)
            })
        return jsonify({"ok": True, "result": result})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/api/content", methods=["GET"])
def get_content():
    """Bosh sahifa matnlarini qaytaradi (admin tahrirlamagan qismlar uchun standart matn ishlatiladi)."""
    try:
        content = dict(DEFAULT_CONTENT)
        content.update(db.get_all_content())
        return jsonify({"ok": True, "result": content})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/api/contact", methods=["POST"])
def submit_contact():
    """Saytdagi 'Biz bilan bog'laning' formasidan kelgan murojaat."""
    try:
        data = request.get_json(force=True) or {}
        name    = (data.get("name") or "").strip()
        phone   = (data.get("phone") or "").strip()
        message = (data.get("message") or "").strip()
        if not name or not message:
            return jsonify({"ok": False, "error": "Ism va xabar matni majburiy"}), 400

        msg_id = db.create_contact_message(name, phone, message)

        import requests as req_lib
        BOT_TOKEN = os.getenv("BOT_TOKEN", "")
        if BOT_TOKEN:
            try:
                text = (
                    f"✉️ <b>YANGI MUROJAAT №{msg_id}</b> (sayt)\n\n"
                    f"👤 Ism: {name}\n"
                    f"📞 Tel: {phone or '—'}\n\n"
                    f"💬 {message}"
                )
                req_lib.post(
                    f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                    json={"chat_id": 286262755, "text": text, "parse_mode": "HTML"},
                    timeout=5
                )
            except Exception:
                pass

        return jsonify({"ok": True, "id": msg_id})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/api/order", methods=["POST"])
def create_order():
    try:
        data          = request.get_json()
        customer_name = data.get("customer_name", "")
        phone         = data.get("phone", "")
        address       = data.get("address", "")
        payment       = data.get("payment", "Naqd")
        delivery      = data.get("delivery", "")
        items         = data.get("items", [])
        location_lat  = data.get("location_lat")
        location_lon  = data.get("location_lon")

        if not customer_name or not phone or not address or not items:
            return jsonify({"ok": False, "error": "Majburiy maydonlar to'ldirilmagan"}), 400

        cart_items = []
        gross = 0
        for it in items:
            product = db.get_product(it["id"])
            if not product:
                continue
            qty  = int(it.get("qty", 1))
            size = it.get("size")
            cart_items.append({
                "product_id": product["id"],
                "name":       product["name"],
                "price":      product["price"],
                "quantity":   qty,
                "size":       size
            })
            gross += product["price"] * qty

        if not cart_items:
            return jsonify({"ok": False, "error": "Mahsulotlar topilmadi"}), 400

        pct          = 10 if gross >= 500000 else 5
        discount_amt = int(gross * pct / 100)
        final_price  = gross - discount_amt

        order_id = db.create_order(
            user_id=0,
            customer_name=customer_name,
            phone=phone,
            address=address,
            payment=payment,
            delivery=delivery,
            items=cart_items,
            total=final_price,
            discount_pct=pct,
            discount_amt=discount_amt
        )

        # Admin ga Telegram xabar
        import requests as req_lib
        BOT_TOKEN = os.getenv("BOT_TOKEN", "")

        items_text = "\n".join([
            f"  • {i['name']}{' ['+i['size']+']' if i.get('size') else ''} x{i['quantity']} = {i['price']*i['quantity']:,} so'm"
            for i in cart_items
        ])
        disc_line = f"\n🎁 Chegirma ({pct}%): -{discount_amt:,} so'm" if discount_amt > 0 else ""

        geo_line = ""
        if location_lat and location_lon:
            geo_line = (
                f"\n📡 Geo: {location_lat:.5f}, {location_lon:.5f}"
                f"\n🗺️ https://www.google.com/maps?q={location_lat},{location_lon}"
            )

        delivery_line = f"\n🚚 Dastavka: {delivery}" if delivery else ""
        msg = (
            f"🆕 <b>YANGI BUYURTMA №{order_id}</b> (WEB)\n\n"
            f"👤 Mijoz: {customer_name}\n"
            f"📞 Tel: {phone}\n"
            f"📍 Manzil: {address}"
            f"{geo_line}"
            f"{delivery_line}\n"
            f"💳 To'lov: {payment}\n\n"
            f"🛒 Mahsulotlar:\n{items_text}\n\n"
            f"💰 Asl narx: {gross:,} so'm"
            f"{disc_line}\n"
            f"✅ <b>To'lov: {final_price:,} so'm</b>"
        )

        if BOT_TOKEN:
            try:
                req_lib.post(
                    f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                    json={"chat_id": 286262755, "text": msg, "parse_mode": "HTML"},
                    timeout=5
                )
            except Exception:
                pass

        return jsonify({
            "ok":           True,
            "order_id":     order_id,
            "discount_pct": pct,
            "discount_amt": discount_amt,
            "final":        final_price
        })

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/api/photo/<int:product_id>", methods=["GET"])
def get_photo(product_id):
    """Telegram file_id orqali yangi photo_url olish"""
    try:
        import requests as req_lib
        product = db.get_product(product_id)
        if not product or not product.get('photo_id'):
            return jsonify({"ok": False, "error": "Rasm yo'q"}), 404
        BOT_TOKEN = os.getenv("BOT_TOKEN", "")
        photo_id  = product['photo_id']
        # Telegram dan yangi URL olish
        r = req_lib.get(
            f"https://api.telegram.org/bot{BOT_TOKEN}/getFile",
            params={"file_id": photo_id},
            timeout=5
        )
        data = r.json()
        if data.get("ok"):
            file_path = data["result"]["file_path"]
            new_url   = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"
            # Bazaga saqlash
            db.update_product_field(product_id, 'photo_url', new_url)
            return jsonify({"ok": True, "photo_url": new_url})
        return jsonify({"ok": False, "error": "Telegram xatosi"}), 500
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/photos/<filename>")
def serve_photo(filename):
    """Serverda saqlangan rasmlarni beradi"""
    return send_from_directory(PHOTOS_DIR, filename)

@app.route("/admin")
def admin_page():
    return send_file("admin.html")


# ══════════════════════════════════════
# ADMIN — AUTH
# ══════════════════════════════════════
@app.route("/api/admin/login", methods=["POST"])
def admin_login():
    try:
        data = request.get_json(force=True) or {}
        username = (data.get("username") or "").strip()
        password = data.get("password") or ""
        if not username or not password:
            return jsonify({"ok": False, "error": "Login va parol kiriting"}), 400
        admin = db.get_site_admin_by_username(username)
        if not admin or not check_password_hash(admin["password_hash"], password):
            return jsonify({"ok": False, "error": "Login yoki parol noto'g'ri"}), 401
        token = secrets.token_hex(32)
        db.create_session(token, admin["id"])
        return jsonify({
            "ok": True,
            "token": token,
            "admin": {"username": admin["username"], "full_name": admin["full_name"], "role": admin["role"]}
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/api/admin/logout", methods=["POST"])
@require_auth()
def admin_logout():
    auth = request.headers.get("Authorization", "")
    token = auth.split(" ", 1)[1] if auth.startswith("Bearer ") else auth
    db.delete_session(token)
    return jsonify({"ok": True})

@app.route("/api/admin/me", methods=["GET"])
@require_auth()
def admin_me():
    a = request.admin
    return jsonify({"ok": True, "admin": {"username": a["username"], "full_name": a["full_name"], "role": a["role"]}})


# ══════════════════════════════════════
# ADMIN — CATEGORIES
# ══════════════════════════════════════
@app.route("/api/admin/categories", methods=["POST"])
@require_auth()
def admin_add_category():
    try:
        data = request.get_json(force=True) or {}
        name = (data.get("name") or "").strip()
        if not name:
            return jsonify({"ok": False, "error": "Kategoriya nomi kerak"}), 400
        cat_id = db.add_category(name, bool(data.get("has_sizes")))
        return jsonify({"ok": True, "id": cat_id})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/api/admin/categories/<int:cat_id>", methods=["PUT"])
@require_auth()
def admin_update_category(cat_id):
    try:
        data = request.get_json(force=True) or {}
        db.update_category(
            cat_id,
            name=data.get("name"),
            has_sizes=data.get("has_sizes") if "has_sizes" in data else None
        )
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/api/admin/categories/<int:cat_id>", methods=["DELETE"])
@require_auth()
def admin_delete_category(cat_id):
    try:
        db.delete_category(cat_id)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# ══════════════════════════════════════
# ADMIN — PRODUCTS
# ══════════════════════════════════════
def _save_uploaded_photo(file_storage):
    """Yuklangan rasm faylini PHOTOS_DIR ga saqlab, uning URL'ini qaytaradi."""
    if not file_storage or not file_storage.filename:
        return None
    ext = secure_filename(file_storage.filename).rsplit(".", 1)[-1].lower() if "." in file_storage.filename else ""
    if ext not in ALLOWED_PHOTO_EXT:
        raise ValueError("Ruxsat etilmagan rasm formati")
    filename = f"{uuid.uuid4().hex}.{ext}"
    file_storage.save(os.path.join(PHOTOS_DIR, filename))
    api_base = os.getenv("API_BASE_URL", request.host_url.rstrip("/"))
    return f"{api_base}/photos/{filename}"

@app.route("/api/admin/products", methods=["GET"])
@require_auth()
def admin_list_products():
    try:
        return jsonify({"ok": True, "result": db.get_all_products()})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/api/admin/products", methods=["POST"])
@require_auth()
def admin_add_product():
    try:
        form = request.form
        name = (form.get("name") or "").strip()
        price = form.get("price", type=int)
        category_id = form.get("category_id", type=int)
        if not name or price is None or not category_id:
            return jsonify({"ok": False, "error": "Nomi, narxi va kategoriyasi majburiy"}), 400
        photo_url = _save_uploaded_photo(request.files.get("photo"))
        product_id = db.add_product(
            name=name, price=price,
            description=form.get("description", ""),
            category_id=category_id,
            photo_url=photo_url,
            sizes=form.get("sizes") or None
        )
        return jsonify({"ok": True, "id": product_id})
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/api/admin/products/<int:product_id>", methods=["PUT"])
@require_auth()
def admin_update_product(product_id):
    try:
        form = request.form
        fields = {}
        for key in ("name", "description", "sizes"):
            if key in form:
                fields[key] = form.get(key)
        if "price" in form:
            fields["price"] = form.get("price", type=int)
        if "category_id" in form:
            fields["category_id"] = form.get("category_id", type=int)
        if request.files.get("photo"):
            photo_url = _save_uploaded_photo(request.files.get("photo"))
            if photo_url:
                fields["photo_url"] = photo_url
        if fields:
            db.update_product(product_id, **fields)
        return jsonify({"ok": True})
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/api/admin/products/<int:product_id>", methods=["DELETE"])
@require_auth()
def admin_delete_product(product_id):
    try:
        db.delete_product(product_id)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# ══════════════════════════════════════
# ADMIN — BOSH SAHIFA MATNLARI
# ══════════════════════════════════════
@app.route("/api/admin/content", methods=["GET"])
@require_auth()
def admin_get_content():
    try:
        content = dict(DEFAULT_CONTENT)
        content.update(db.get_all_content())
        return jsonify({"ok": True, "result": content})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/api/admin/content", methods=["PUT"])
@require_auth()
def admin_update_content():
    try:
        data = request.get_json(force=True) or {}
        allowed = set(DEFAULT_CONTENT.keys())
        to_save = {k: str(v) for k, v in data.items() if k in allowed}
        if not to_save:
            return jsonify({"ok": False, "error": "Yangilanadigan maydon topilmadi"}), 400
        db.set_content_bulk(to_save)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# ══════════════════════════════════════
# ADMIN — MUROJAATLAR (contact-form xabarlari)
# ══════════════════════════════════════
@app.route("/api/admin/messages", methods=["GET"])
@require_auth()
def admin_list_messages():
    try:
        return jsonify({"ok": True, "result": db.list_contact_messages()})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/api/admin/messages/<int:message_id>/read", methods=["PUT"])
@require_auth()
def admin_mark_message_read(message_id):
    try:
        db.mark_message_read(message_id)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/api/admin/messages/<int:message_id>", methods=["DELETE"])
@require_auth()
def admin_delete_message(message_id):
    try:
        db.delete_contact_message(message_id)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# ══════════════════════════════════════
# ADMIN — XODIMLAR (faqat role=admin)
# ══════════════════════════════════════
@app.route("/api/admin/users", methods=["GET"])
@require_auth(role="admin")
def admin_list_users():
    try:
        return jsonify({"ok": True, "result": db.list_site_admins()})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/api/admin/users", methods=["POST"])
@require_auth(role="admin")
def admin_create_user():
    try:
        data = request.get_json(force=True) or {}
        username = (data.get("username") or "").strip()
        password = data.get("password") or ""
        full_name = data.get("full_name", "")
        role = data.get("role") if data.get("role") in ("admin", "worker") else "worker"
        if not username or len(password) < 4:
            return jsonify({"ok": False, "error": "Login kiriting, parol kamida 4 belgi"}), 400
        if db.username_exists(username):
            return jsonify({"ok": False, "error": "Bu login band"}), 400
        admin_id = db.create_site_admin(username, generate_password_hash(password), full_name, role)
        return jsonify({"ok": True, "id": admin_id})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/api/admin/users/<int:admin_id>", methods=["DELETE"])
@require_auth(role="admin")
def admin_delete_user(admin_id):
    try:
        if admin_id == request.admin["id"]:
            return jsonify({"ok": False, "error": "O'zingizni o'chira olmaysiz"}), 400
        db.deactivate_site_admin(admin_id)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    port = int(os.getenv("API_PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False)

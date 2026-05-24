"""
BUYUK KIDS — Flask API
Veb-sahifa uchun kategoriya va mahsulotlarni beradi
"""
from flask import Flask, jsonify, request, send_file
from flask_cors import CORS
from database import Database
import os

app = Flask(__name__)
CORS(app)

DB_PATH = os.getenv("DB_PATH", "shop.db")
db = Database(DB_PATH)

db.init_db()

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

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    port = int(os.getenv("API_PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False)

"""
BUYUK KIDS — Flask API
Veb-sahifa uchun kategoriya va mahsulotlarni beradi
"""
from flask import Flask, jsonify
from flask_cors import CORS
from database import Database
import os

app = Flask(__name__)
CORS(app)  # Barcha domenlardan so'rov qabul qiladi

DB_PATH = os.getenv("DB_PATH", "shop.db")
db = Database(DB_PATH)

@app.route("/api/categories", methods=["GET"])
def get_categories():
    """Barcha kategoriyalar"""
    try:
        categories = db.get_categories()
        return jsonify({"ok": True, "result": categories})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/api/products/<int:cat_id>", methods=["GET"])
def get_products(cat_id):
    """Kategoriya bo'yicha mahsulotlar"""
    try:
        products = db.get_products_by_category(cat_id)
        # photo_id ni veb uchun olib tashlaymiz (Telegram file_id vebda ishlamaydi)
        result = []
        for p in products:
            result.append({
                "id": p["id"],
                "name": p["name"],
                "price": p["price"],
                "description": p.get("description", ""),
                "sizes": p.get("sizes", None),
                "has_photo": bool(p.get("photo_id"))
            })
        return jsonify({"ok": True, "result": result})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/api/search", methods=["GET"])
def search():
    """Mahsulot qidirish"""
    from flask import request
    query = request.args.get("q", "").strip()
    if len(query) < 2:
        return jsonify({"ok": False, "error": "Kamida 2 harf"}), 400
    try:
        products = db.search_products(query)
        result = []
        for p in products:
            result.append({
                "id": p["id"],
                "name": p["name"],
                "price": p["price"],
                "description": p.get("description", ""),
                "sizes": p.get("sizes", None),
                "cat_name": p.get("cat_name", ""),
                "has_photo": bool(p.get("photo_id"))
            })
        return jsonify({"ok": True, "result": result})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    port = int(os.getenv("API_PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False)

@app.route("/api/order", methods=["POST"])
def create_order():
    try:
        data = request.get_json()
        customer_name = data.get("customer_name", "")
        phone         = data.get("phone", "")
        address       = data.get("address", "")
        payment       = data.get("payment", "Naqd")
        items         = data.get("items", [])
        location_lat  = data.get("location_lat")
        location_lon  = data.get("location_lon")

        if not customer_name or not phone or not address or not items:
            return jsonify({"ok": False, "error": "Majburiy maydonlar"}), 400

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
            user_id=0, customer_name=customer_name,
            phone=phone, address=address, payment=payment,
            items=cart_items, total=final_price,
            discount_pct=pct, discount_amt=discount_amt
        )

        import requests as req_lib
        BOT_TOKEN = os.getenv("BOT_TOKEN", "")
        items_text = "\n".join([
            f"  • {i['name']}{' ['+i['size']+']' if i.get('size') else ''} x{i['quantity']} = {i['price']*i['quantity']:,} so'm"
            for i in cart_items
        ])
        disc_line = f"\n🎁 Chegirma ({pct}%): -{discount_amt:,} so'm" if discount_amt > 0 else ""
        geo_line  = ""
        if location_lat and location_lon:
            geo_line = f"\n📡 {location_lat:.5f}, {location_lon:.5f}\n🗺️ https://www.google.com/maps?q={location_lat},{location_lon}"

        msg = (
            f"🆕 <b>YANGI BUYURTMA №{order_id}</b> (WEB)\n\n"
            f"👤 {customer_name}\n📞 {phone}\n📍 {address}{geo_line}\n"
            f"💳 {payment}\n\n🛒 Mahsulotlar:\n{items_text}\n\n"
            f"💰 {gross:,} so'm{disc_line}\n"
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
            "ok": True, "order_id": order_id,
            "discount_pct": pct, "discount_amt": discount_amt,
            "final": final_price
        })

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

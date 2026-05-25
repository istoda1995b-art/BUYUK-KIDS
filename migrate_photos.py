#!/usr/bin/env python3
"""
Eski mahsulot rasmlarini Telegram dan serverga ko'chirish
Bu scriptni Railway da bir marta ishlatiladi
"""
import os
import uuid
import requests
from database import Database

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
DB_PATH    = os.getenv("DB_PATH", "shop.db")
API_BASE   = os.getenv("API_BASE_URL", "https://buyuk-kids-production.up.railway.app")
PHOTOS_DIR = os.path.join(os.path.dirname(__file__), "photos")

os.makedirs(PHOTOS_DIR, exist_ok=True)
db = Database(DB_PATH)

def migrate():
    with db.get_connection() as conn:
        products = conn.execute(
            "SELECT id, name, photo_id, photo_url FROM products WHERE is_active=1 AND photo_id IS NOT NULL"
        ).fetchall()

    print(f"Jami {len(products)} ta mahsulot rasmi bor")
    ok = 0
    fail = 0

    for p in products:
        pid      = p['id']
        name     = p['name']
        photo_id = p['photo_id']
        old_url  = p['photo_url'] or ''

        # Agar allaqachon serverda saqlangan bo'lsa — o'tkazib yuborish
        if old_url.startswith(API_BASE + '/photos/'):
            print(f"  ✅ [{pid}] {name} — allaqachon serverda")
            ok += 1
            continue

        try:
            # Telegram dan file_path olish
            r = requests.get(
                f"https://api.telegram.org/bot{BOT_TOKEN}/getFile",
                params={"file_id": photo_id},
                timeout=10
            )
            data = r.json()
            if not data.get("ok"):
                print(f"  ❌ [{pid}] {name} — Telegram xatosi: {data}")
                fail += 1
                continue

            file_path = data["result"]["file_path"]
            tg_url    = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"
            ext       = file_path.split('.')[-1]
            filename  = f"{uuid.uuid4().hex}.{ext}"
            filepath  = os.path.join(PHOTOS_DIR, filename)

            # Rasmni yuklab olish
            img_r = requests.get(tg_url, timeout=15)
            if img_r.status_code != 200:
                print(f"  ❌ [{pid}] {name} — Rasm yuklanmadi: {img_r.status_code}")
                fail += 1
                continue

            # Serverga saqlash
            with open(filepath, 'wb') as f:
                f.write(img_r.content)

            # Bazani yangilash
            new_url = f"{API_BASE}/photos/{filename}"
            with db.get_connection() as conn:
                conn.execute(
                    "UPDATE products SET photo_url=? WHERE id=?",
                    (new_url, pid)
                )

            print(f"  ✅ [{pid}] {name} — saqlandi: {filename}")
            ok += 1

        except Exception as e:
            print(f"  ❌ [{pid}] {name} — xato: {e}")
            fail += 1

    print(f"\n{'='*40}")
    print(f"✅ Muvaffaqiyatli: {ok} ta")
    print(f"❌ Xato: {fail} ta")
    print(f"{'='*40}")

if __name__ == "__main__":
    migrate()

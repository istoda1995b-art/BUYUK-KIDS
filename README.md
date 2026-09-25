# BUYUK KIDS — brend sayt + dastavka (bitta server)

| Manzil | Nima |
|---|---|
| `/` | Buyuk Kids brend sayti (kids_site/, FastAPI) |
| `/site-admin` | Brend sayt admin paneli (matnlar, kategoriyalar, blog, do'konlar, arizalar) |
| `/shop` | Dastavka do'koni (buyukkids_shop.html) |
| `/admin` | Dastavka admin paneli (mahsulotlar, buyurtmalar) — o'zgarmadi |
| `/api/*`, `/photos/*`, `/health` | Dastavka API (api.py, Flask) — o'zgarmadi |
| bot.py | Telegram bot — o'zgarmadi |

`server.py` — ikkala ilovani birlashtiradi: FastAPI o'z yo'llarini oladi, qolgani Flask'ga o'tadi.

## Railway o'zgaruvchilari
Eskilari qoladi: `BOT_TOKEN`, `DB_PATH`, `API_BASE_URL`, `BOOTSTRAP_ADMIN_*`.
Yangilari:
- `ADMIN_USER`, `ADMIN_PASSWORD` — /site-admin uchun login/parol
- `SECRET_KEY` — uzun tasodifiy satr
- `TG_CHAT_ID` — (ixtiyoriy) brend sayt arizalari shu chatga keladi; `TG_BOT_TOKEN` berilmasa ham bo'ladi
- `DATABASE_URL` — (ixtiyoriy) Postgres. Bo'lmasa brend sayt `DB_PATH` papkasida `kids_site.db` faylini ishlatadi.

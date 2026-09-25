"""
BUYUK KIDS — yagona server.
  /            -> Buyuk Kids brend sayti (FastAPI, kids_site/)
  /site-admin  -> brend sayt admin paneli
  /shop        -> dastavka do'koni (buyukkids_shop.html)
  /admin       -> dastavka admin paneli (o'zgarmadi)
  /api/*, /photos/*, /health -> dastavka API (Flask, api.py — o'zgarmadi)
Telegram bot (bot.py) alohida jarayon sifatida ishlaydi (railway.toml).
"""
from pathlib import Path
from fastapi.responses import FileResponse, RedirectResponse
from a2wsgi import WSGIMiddleware

from kids_site.main import app          # FastAPI brend sayt
from api import app as shop_app         # Flask dastavka API

ROOT = Path(__file__).parent


@app.get("/shop", include_in_schema=False)
async def shop_page():
    return FileResponse(ROOT / "buyukkids_shop.html", headers={"Cache-Control": "no-cache"})


@app.get("/shop/", include_in_schema=False)
async def shop_slash():
    return RedirectResponse("/shop", status_code=301)


# Qolgan hamma so'rovlar (/api, /admin, /photos, /health ...) — Flask dastavka ilovasiga
app.mount("/", WSGIMiddleware(shop_app, workers=8))

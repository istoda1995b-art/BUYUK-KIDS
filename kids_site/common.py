import os
from datetime import datetime
from pathlib import Path
from fastapi import Request
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from .i18n import t, loc, LANGS
from .models import Setting

BASE_DIR = Path(__file__).parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


def media_url(mid) -> str:
    return f"/media/{mid}" if mid else ""


def nl2p(text: str) -> str:
    from markupsafe import escape, Markup
    parts = [p.strip() for p in (text or "").split("\n\n") if p.strip()]
    return Markup("".join(f"<p>{escape(p).replace(chr(10), Markup('<br>'))}</p>" for p in parts))


def qr_svg(data: str) -> str:
    """Haqiqiy QR (sayt manzili) — inline SVG."""
    from markupsafe import Markup
    try:
        import qrcode
        q = qrcode.QRCode(border=0, error_correction=qrcode.constants.ERROR_CORRECT_M)
        q.add_data(data)
        q.make(fit=True)
        m = q.get_matrix()
        n = len(m)
        rects = "".join(f'<rect x="{x}" y="{y}" width="1.02" height="1.02"/>'
                        for y, row in enumerate(m) for x, v in enumerate(row) if v)
        return Markup(f'<svg class="qr" viewBox="0 0 {n} {n}" shape-rendering="crispEdges"><g fill="#1E2A4A">{rects}</g></svg>')
    except Exception:
        return Markup("")


templates.env.globals.update(media_url=media_url, qr_svg=qr_svg)
templates.env.filters["nl2p"] = nl2p


def nbsp_num(v: str) -> str:
    """10 000+ bo'linib ketmasligi uchun raqamlar orasidagi bo'shliqni nbsp ga almashtiradi."""
    import re
    from markupsafe import Markup, escape
    return Markup(re.sub(r"(?<=\d) (?=\d)", "&nbsp;", str(escape(v))))


templates.env.filters["nbsp_num"] = nbsp_num


def render(name: str, context: dict, status_code: int = 200):
    return templates.TemplateResponse(request=context["request"], name=name, context=context,
                                      status_code=status_code)


def get_lang(request: Request) -> str:
    q = request.query_params.get("lang")
    if q in LANGS:
        return q
    c = request.cookies.get("lang")
    return c if c in LANGS else "uz"


async def load_settings(session, lang: str) -> dict:
    rows = (await session.execute(select(Setting))).scalars().all()
    out = {}
    for r in rows:
        v = r.value_ru if lang == "ru" and r.value_ru else r.value_uz
        out[r.key] = v or ""
    return out


async def ctx(request: Request, session, **extra) -> dict:
    lang = get_lang(request)
    S = await load_settings(session, lang)
    base = {
        "request": request,
        "lang": lang,
        "S": S,
        "t": lambda k: t(k, lang),
        "L": lambda obj, f: loc(obj, f, lang),
        "path": request.url.path,
        "year": datetime.now().year,
        "base_url": str(request.base_url).rstrip("/"),
        "site_url": (os.getenv("SITE_URL") or str(request.base_url)).rstrip("/"),
        "order_href": S.get("order_url") or "/shop",
        "order_ext": (S.get("order_url") or "").startswith("http"),
    }
    base.update(extra)
    return base


async def notify_telegram(text: str):
    token = os.getenv("TG_BOT_TOKEN") or os.getenv("BOT_TOKEN")
    chat = os.getenv("TG_CHAT_ID")
    if not token or not chat:
        return
    try:
        import httpx
        async with httpx.AsyncClient(timeout=10) as c:
            await c.post(f"https://api.telegram.org/bot{token}/sendMessage",
                         json={"chat_id": chat, "text": text})
    except Exception:
        pass

import io
import os
import re
import secrets
from fastapi import APIRouter, Request, Depends, HTTPException, UploadFile
from fastapi.responses import RedirectResponse
from sqlalchemy import select, func, delete

from .db import get_session
from .models import Media, Setting, StatCard, Store, Post, Vacancy, Submission, Category
from .seed import SETTINGS
from .common import templates, render

router = APIRouter(prefix="/site-admin")

ADMIN_USER = os.getenv("ADMIN_USER", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")


def require_admin(request: Request):
    if not request.session.get("admin"):
        raise HTTPException(303, headers={"Location": "/site-admin/login"})
    return True


async def save_upload(session, up: UploadFile | None) -> int | None:
    if not up or not up.filename:
        return None
    raw = await up.read()
    if not raw:
        return None
    ctype = up.content_type or "application/octet-stream"
    if not ctype.startswith("image/"):
        return None
    data = raw
    if ctype != "image/svg+xml" and ctype != "image/gif":
        try:
            from PIL import Image, ImageOps
            im = ImageOps.exif_transpose(Image.open(io.BytesIO(raw)))
            if max(im.size) > 2000:
                im.thumbnail((2000, 2000))
            buf = io.BytesIO()
            if im.mode in ("RGBA", "LA", "P"):
                im = im.convert("RGBA")
            im.save(buf, "WEBP", quality=85)
            data, ctype = buf.getvalue(), "image/webp"
        except Exception:
            pass
    m = Media(filename=up.filename[:255], content_type=ctype, data=data)
    session.add(m)
    await session.flush()
    return m.id


def slugify(s: str) -> str:
    tr = str.maketrans({"'": "", "ʻ": "", "ʼ": "", "‘": "", "’": ""})
    s = s.translate(tr).lower()
    cyr = "абвгдеёжзийклмнопрстуфхцчшщъыьэюяўқғҳ"
    lat = ["a","b","v","g","d","e","yo","zh","z","i","y","k","l","m","n","o","p","r","s","t","u","f","h","ts","ch","sh","sch","","i","","e","yu","ya","o","q","g","h"]
    s = "".join(lat[cyr.index(c)] if c in cyr else c for c in s)
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s[:150] or secrets.token_hex(4)


# ---------------- CRUD config ----------------
# (name, label, type)  types: text textarea int float bool image color select:<a|b>
TOYS = "bear|blocks|pyramid|ball|duck|car|tshirt|bottle|rocket|stroller|backpack|cosmetic"

CRUD = {
    "categories": {
        "model": Category, "title": "Kategoriyalar", "order": (Category.sort, Category.id),
        "cols": [("name_uz", "Nomi"), ("toy", "Rasm (standart)"), ("color", "Fon")],
        "fields": [
            ("name_uz", "Nomi (UZ)", "text"), ("name_ru", "Nomi (RU)", "text"),
            ("image_id", "O'z rasmingiz (shaffof PNG yaxshi — bo'lmasa quyidagi chizma)", "image"),
            ("toy", "Standart chizma", "select:" + TOYS), ("color", "Fon rangi", "color"),
            ("link", "Havola (bo'sh = dastavka sayti)", "text"), ("sort", "Tartib", "int"),
        ],
    },
    "stores": {
        "model": Store, "title": "Do'konlar", "order": (Store.sort, Store.id),
        "cols": [("name", "Nomi"), ("hours", "Ish vaqti"), ("rating", "Reyting"), ("is_active", "Faol")],
        "fields": [
            ("name", "Nomi", "text"), ("address_uz", "Manzil (UZ)", "text"), ("address_ru", "Manzil (RU)", "text"),
            ("phone", "Telefon", "text"), ("hours", "Ish vaqti", "text"), ("rating", "Reyting (0–5)", "float"),
            ("lat", "Kenglik (lat) — Yandex xaritadan", "float"), ("lon", "Uzunlik (lon)", "float"),
            ("image_id", "Rasm", "image"), ("sort", "Tartib", "int"), ("is_active", "Faol", "bool"),
        ],
    },
    "posts": {
        "model": Post, "title": "Blog maqolalari", "order": (Post.created_at.desc(), Post.id.desc()),
        "cols": [("title_uz", "Sarlavha"), ("slug", "Slug"), ("is_published", "Chop etilgan")],
        "fields": [
            ("title_uz", "Sarlavha (UZ)", "text"), ("title_ru", "Sarlavha (RU)", "text"),
            ("slug", "Slug (bo'sh qoldirsangiz avtomatik)", "text"),
            ("excerpt_uz", "Qisqa matn (UZ)", "textarea"), ("excerpt_ru", "Qisqa matn (RU)", "textarea"),
            ("body_uz", "Matn (UZ) — xatboshilar bo'sh qator bilan", "textarea-lg"),
            ("body_ru", "Matn (RU)", "textarea-lg"),
            ("image_id", "Rasm (1200x800)", "image"), ("is_published", "Chop etilgan", "bool"),
        ],
    },
    "vacancies": {
        "model": Vacancy, "title": "Vakansiyalar", "order": (Vacancy.sort, Vacancy.id),
        "cols": [("title_uz", "Lavozim"), ("salary", "Maosh"), ("is_active", "Faol")],
        "fields": [
            ("title_uz", "Lavozim (UZ)", "text"), ("title_ru", "Lavozim (RU)", "text"),
            ("desc_uz", "Tavsif (UZ)", "textarea"), ("desc_ru", "Tavsif (RU)", "textarea"),
            ("salary", "Maosh", "text"), ("location", "Joylashuv", "text"),
            ("sort", "Tartib", "int"), ("is_active", "Faol", "bool"),
        ],
    },
    "stats": {
        "model": StatCard, "title": "Statistika kartochkalari", "order": (StatCard.sort, StatCard.id),
        "cols": [("value", "Qiymat"), ("label_uz", "Matn"), ("color", "Rang")],
        "fields": [
            ("value", "Qiymat (masalan 10 000+)", "text"), ("label_uz", "Matn (UZ)", "text"),
            ("label_ru", "Matn (RU)", "text"), ("color", "Fon rangi", "color"),
            ("icon", "Ikonka (rasm yuklanmasa)", "select:clock|box|heart|store|star|gift"),
            ("image_id", "Rasm (ixtiyoriy, shaffof PNG)", "image"), ("sort", "Tartib", "int"),
        ],
    },
}


async def base_ctx(request, session, **kw):
    unread = (await session.execute(select(func.count(Submission.id)).where(Submission.is_read.is_(False)))).scalar()
    d = {"request": request, "unread": unread, "path": request.url.path, "crud": CRUD}
    d.update(kw)
    return d


# ---------------- auth ----------------
@router.get("/login")
async def login_form(request: Request):
    return render("admin/login.html", {"request": request, "error": None})


@router.post("/login")
async def login(request: Request):
    f = await request.form()
    ok = secrets.compare_digest(str(f.get("username", "")), ADMIN_USER) and \
        secrets.compare_digest(str(f.get("password", "")), ADMIN_PASSWORD)
    if not ok:
        return render("admin/login.html", {"request": request, "error": "Login yoki parol xato"},
                                          status_code=401)
    request.session["admin"] = True
    return RedirectResponse("/site-admin", status_code=303)


@router.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/site-admin/login", status_code=303)


# ---------------- dashboard ----------------
@router.get("")
async def dashboard(request: Request, _=Depends(require_admin), session=Depends(get_session)):
    counts = {}
    for key, cfg in CRUD.items():
        counts[key] = (await session.execute(select(func.count(cfg["model"].id)))).scalar()
    subs = (await session.execute(select(Submission).order_by(Submission.id.desc()).limit(8))).scalars().all()
    return render("admin/dashboard.html", await base_ctx(
        request, session, counts=counts, subs=subs))


# ---------------- settings ----------------
GROUPS = [
    ("Bosh sahifa — Hero", "hero_"), ("Buyurtma / dastavka sayti", "order_|delivery_"), ("Kategoriyalar", "categories_"), ("Afzalliklar bo'limi", "features_"), ("Keshbek", "cashback_|loyalty_"),
    ("Bo'lim sarlavhalari", "blog_|stores_"), ("Sahifalar", "about_|partners_|career_"),
    ("Kontaktlar va footer", "footer_|address|email|phone|telegram|instagram|youtube|facebook"),
]


@router.get("/settings")
async def settings_form(request: Request, _=Depends(require_admin), session=Depends(get_session)):
    rows = {r.key: r for r in (await session.execute(select(Setting))).scalars().all()}
    groups = []
    for title, pat in GROUPS:
        items = [(k, SETTINGS[k], rows.get(k)) for k in SETTINGS if re.match(pat, k)]
        groups.append((title, items))
    return render("admin/settings.html", await base_ctx(
        request, session, groups=groups, saved=request.query_params.get("saved")))


@router.post("/settings")
async def settings_save(request: Request, _=Depends(require_admin), session=Depends(get_session)):
    f = await request.form()
    rows = {r.key: r for r in (await session.execute(select(Setting))).scalars().all()}
    for key, (_uz, _ru, _label, typ) in SETTINGS.items():
        row = rows.get(key) or Setting(key=key, value_uz="", value_ru="")
        if key not in rows:
            session.add(row)
        if typ == "image":
            mid = await save_upload(session, f.get(key))
            if mid:
                row.value_uz = str(mid)
            elif f.get(f"{key}__remove"):
                row.value_uz = ""
        else:
            if f"{key}__uz" in f:
                row.value_uz = str(f.get(f"{key}__uz", ""))
            if f"{key}__ru" in f:
                row.value_ru = str(f.get(f"{key}__ru", ""))
    await session.commit()
    return RedirectResponse("/site-admin/settings?saved=1", status_code=303)


# ---------------- submissions ----------------
@router.get("/submissions")
async def submissions(request: Request, kind: str = "", _=Depends(require_admin), session=Depends(get_session)):
    q = select(Submission).order_by(Submission.id.desc())
    if kind:
        q = q.where(Submission.kind == kind)
    subs = (await session.execute(q.limit(500))).scalars().all()
    return render("admin/submissions.html", await base_ctx(
        request, session, subs=subs, kind=kind))


@router.post("/submissions/{sid}/read")
async def sub_read(sid: int, _=Depends(require_admin), session=Depends(get_session)):
    s = await session.get(Submission, sid)
    if s:
        s.is_read = not s.is_read
        await session.commit()
    return RedirectResponse("/site-admin/submissions", status_code=303)


@router.post("/submissions/{sid}/delete")
async def sub_delete(sid: int, _=Depends(require_admin), session=Depends(get_session)):
    await session.execute(delete(Submission).where(Submission.id == sid))
    await session.commit()
    return RedirectResponse("/site-admin/submissions", status_code=303)


# ---------------- generic CRUD ----------------
def _cfg(entity):
    cfg = CRUD.get(entity)
    if not cfg:
        raise HTTPException(404)
    return cfg


@router.get("/{entity}")
async def crud_list(entity: str, request: Request, _=Depends(require_admin), session=Depends(get_session)):
    cfg = _cfg(entity)
    items = (await session.execute(select(cfg["model"]).order_by(*cfg["order"]))).scalars().all()
    return render("admin/list.html", await base_ctx(
        request, session, entity=entity, cfg=cfg, items=items))


@router.get("/{entity}/{item_id}")
async def crud_form(entity: str, item_id: str, request: Request, _=Depends(require_admin),
                    session=Depends(get_session)):
    cfg = _cfg(entity)
    item = None
    if item_id != "new":
        item = await session.get(cfg["model"], int(item_id))
        if not item:
            raise HTTPException(404)
    return render("admin/form.html", await base_ctx(
        request, session, entity=entity, cfg=cfg, item=item, error=None))


@router.post("/{entity}/{item_id}")
async def crud_save(entity: str, item_id: str, request: Request, _=Depends(require_admin),
                    session=Depends(get_session)):
    cfg = _cfg(entity)
    Model = cfg["model"]
    item = Model() if item_id == "new" else await session.get(Model, int(item_id))
    if item is None:
        raise HTTPException(404)
    f = await request.form()
    for name, _label, typ in cfg["fields"]:
        if typ == "bool":
            setattr(item, name, bool(f.get(name)))
        elif typ == "image":
            mid = await save_upload(session, f.get(name))
            if mid:
                setattr(item, name, mid)
            elif f.get(f"{name}__remove"):
                setattr(item, name, None)
        elif typ == "int":
            try: setattr(item, name, int(f.get(name) or 0))
            except ValueError: setattr(item, name, 0)
        elif typ == "float":
            try: setattr(item, name, float(str(f.get(name) or 0).replace(",", ".")))
            except ValueError: setattr(item, name, 0.0)
        else:
            setattr(item, name, str(f.get(name, "")).strip())
    if Model is Post:
        item.slug = slugify(item.slug or item.title_uz)
        clash = (await session.execute(select(Post).where(Post.slug == item.slug, Post.id != (item.id or 0)))).scalar()
        if clash:
            item.slug = f"{item.slug}-{secrets.token_hex(2)}"
        item.title_ru = item.title_ru or item.title_uz
    if item_id == "new":
        session.add(item)
    await session.commit()
    return RedirectResponse(f"/site-admin/{entity}", status_code=303)


@router.post("/{entity}/{item_id}/delete")
async def crud_delete(entity: str, item_id: int, _=Depends(require_admin), session=Depends(get_session)):
    cfg = _cfg(entity)
    await session.execute(delete(cfg["model"]).where(cfg["model"].id == item_id))
    await session.commit()
    return RedirectResponse(f"/site-admin/{entity}", status_code=303)

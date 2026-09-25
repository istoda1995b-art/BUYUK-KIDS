import os
from contextlib import asynccontextmanager
from urllib.parse import quote
from fastapi import FastAPI, Request, Depends, Form, HTTPException
from fastapi.responses import Response, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select, or_
from starlette.middleware.sessions import SessionMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from .db import engine, Base, SessionLocal, get_session
from .models import Media, StatCard, Store, Post, Vacancy, Submission, Category
from .seed import seed
from .common import templates, render, ctx, BASE_DIR, notify_telegram
from .i18n import LANGS
from . import admin


@asynccontextmanager
async def lifespan(app):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with SessionLocal() as s:
        await seed(s)
    yield


app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None)
app.add_middleware(SessionMiddleware, secret_key=os.getenv("SECRET_KEY", "change-me-buyuk-kids"),
                   max_age=60 * 60 * 24 * 7)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
app.include_router(admin.router)


def map_url(stores) -> str:
    pts = [s for s in stores if s.lat and s.lon]
    if not pts:
        return ""
    lat = sum(s.lat for s in pts) / len(pts)
    lon = sum(s.lon for s in pts) / len(pts)
    z = 13 if len(pts) == 1 else 11
    pt = "~".join(f"{s.lon},{s.lat},pm2rdm" for s in pts)
    return f"https://yandex.uz/map-widget/v1/?ll={lon},{lat}&z={z}&pt={quote(pt, safe=',~')}"


async def active_stores(session):
    return (await session.execute(
        select(Store).where(Store.is_active.is_(True)).order_by(Store.sort, Store.id))).scalars().all()


# ---------- media ----------
@app.get("/media/{mid}")
async def media(mid: int, session=Depends(get_session)):
    m = await session.get(Media, mid)
    if not m:
        raise HTTPException(404)
    return Response(m.data, media_type=m.content_type,
                    headers={"Cache-Control": "public, max-age=31536000, immutable"})


@app.get("/lang/{code}")
async def set_lang(code: str, next: str = "/"):
    if not next.startswith("/"):
        next = "/"
    r = RedirectResponse(next, status_code=303)
    if code in LANGS:
        r.set_cookie("lang", code, max_age=60 * 60 * 24 * 365, samesite="lax")
    return r


# ---------- SEO ----------
from fastapi.responses import PlainTextResponse


def _site(request: Request) -> str:
    return (os.getenv("SITE_URL") or str(request.base_url)).rstrip("/")


@app.get("/robots.txt", include_in_schema=False)
async def robots(request: Request):
    return PlainTextResponse(
        "User-agent: *\nAllow: /\nDisallow: /site-admin\nDisallow: /admin\nDisallow: /api/\n"
        f"Sitemap: {_site(request)}/sitemap.xml\n")


@app.get("/sitemap.xml", include_in_schema=False)
async def sitemap(request: Request, session=Depends(get_session)):
    base = _site(request)
    urls = ["/", "/shop", "/stores", "/blog", "/about", "/career", "/partners", "/contacts", "/loyalty"]
    slugs = (await session.execute(select(Post.slug).where(Post.is_published.is_(True)))).scalars().all()
    urls += [f"/blog/{s}" for s in slugs]
    body = "".join(f"<url><loc>{base}{u}</loc></url>" for u in urls)
    xml = f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{body}</urlset>'
    return Response(xml, media_type="application/xml")


# ---------- pages ----------
@app.get("/")
async def home(request: Request, session=Depends(get_session)):
    stats = (await session.execute(select(StatCard).order_by(StatCard.sort, StatCard.id))).scalars().all()
    posts = (await session.execute(select(Post).where(Post.is_published.is_(True))
                                   .order_by(Post.created_at.desc(), Post.id.desc()).limit(3))).scalars().all()
    stores = await active_stores(session)
    cats = (await session.execute(select(Category).order_by(Category.sort, Category.id))).scalars().all()
    return render("index.html", await ctx(
        request, session, stats=stats, posts=posts, stores=stores, cats=cats, map_url=map_url(stores)))


@app.get("/stores")
async def stores_page(request: Request, session=Depends(get_session)):
    stores = await active_stores(session)
    return render("stores.html", await ctx(
        request, session, stores=stores, map_url=map_url(stores)))


@app.get("/blog")
async def blog(request: Request, session=Depends(get_session)):
    posts = (await session.execute(select(Post).where(Post.is_published.is_(True))
                                   .order_by(Post.created_at.desc(), Post.id.desc()))).scalars().all()
    return render("blog.html", await ctx(request, session, posts=posts))


@app.get("/blog/{slug}")
async def post(slug: str, request: Request, session=Depends(get_session)):
    p = (await session.execute(select(Post).where(Post.slug == slug, Post.is_published.is_(True)))).scalar()
    if not p:
        raise HTTPException(404)
    more = (await session.execute(select(Post).where(Post.is_published.is_(True), Post.id != p.id)
                                  .order_by(Post.created_at.desc()).limit(3))).scalars().all()
    return render("post.html", await ctx(request, session, post=p, more=more))


@app.get("/about")
async def about(request: Request, session=Depends(get_session)):
    stats = (await session.execute(select(StatCard).order_by(StatCard.sort, StatCard.id))).scalars().all()
    return render("about.html", await ctx(request, session, stats=stats))


@app.get("/career")
async def career(request: Request, session=Depends(get_session)):
    vac = (await session.execute(select(Vacancy).where(Vacancy.is_active.is_(True))
                                 .order_by(Vacancy.sort, Vacancy.id))).scalars().all()
    return render("career.html", await ctx(
        request, session, vacancies=vac, sent=request.query_params.get("sent")))


@app.get("/partners")
async def partners(request: Request, session=Depends(get_session)):
    return render("partners.html", await ctx(
        request, session, sent=request.query_params.get("sent")))


@app.get("/contacts")
async def contacts(request: Request, session=Depends(get_session)):
    stores = await active_stores(session)
    return render("contacts.html", await ctx(
        request, session, stores=stores, map_url=map_url(stores), sent=request.query_params.get("sent")))


@app.get("/loyalty")
async def loyalty(request: Request, session=Depends(get_session)):
    return render("loyalty.html", await ctx(
        request, session, sent=request.query_params.get("sent")))


@app.get("/search")
async def search(request: Request, q: str = "", session=Depends(get_session)):
    posts, stores = [], []
    q = q.strip()[:100]
    if q:
        like = f"%{q}%"
        posts = (await session.execute(select(Post).where(Post.is_published.is_(True), or_(
            Post.title_uz.ilike(like), Post.title_ru.ilike(like),
            Post.body_uz.ilike(like), Post.body_ru.ilike(like))))).scalars().all()
        stores = (await session.execute(select(Store).where(Store.is_active.is_(True), or_(
            Store.name.ilike(like), Store.address_uz.ilike(like), Store.address_ru.ilike(like))))).scalars().all()
    return render("search.html", await ctx(request, session, q=q, posts=posts, stores=stores))


KIND_BACK = {"contact": "/contacts", "partner": "/partners", "career": "/career", "loyalty": "/loyalty"}
KIND_LABEL = {"contact": "📩 Kontakt", "partner": "🤝 Hamkorlik", "career": "💼 Karyera", "loyalty": "🎁 Keshbek"}


@app.post("/submit/{kind}")
async def submit(kind: str, name: str = Form(...), phone: str = Form(...), company: str = Form(""),
                 subject: str = Form(""), message: str = Form(""), website: str = Form(""),
                 session=Depends(get_session)):
    if kind not in KIND_BACK:
        raise HTTPException(404)
    if not website:  # honeypot: botlar to'ldiradi
        s = Submission(kind=kind, name=name[:200], phone=phone[:50], company=company[:200],
                       subject=subject[:300], message=message[:5000])
        session.add(s)
        await session.commit()
        lines = [f"{KIND_LABEL[kind]} — Buyuk Kids sayti", f"👤 {name}", f"📞 {phone}"]
        if company: lines.append(f"🏢 {company}")
        if subject: lines.append(f"📌 {subject}")
        if message: lines.append(f"💬 {message}")
        await notify_telegram("\n".join(lines))
    return RedirectResponse(f"{KIND_BACK[kind]}?sent=1#form", status_code=303)


@app.exception_handler(StarletteHTTPException)
async def http_exc(request: Request, exc: StarletteHTTPException):
    if exc.status_code == 404 and not request.url.path.startswith(("/site-admin", "/media", "/static")):
        async with SessionLocal() as s:
            return render("404.html", await ctx(request, s), status_code=404)
    if exc.status_code in (302, 303) and exc.headers:
        return RedirectResponse(exc.headers.get("Location", "/"), status_code=exc.status_code)
    return Response(str(exc.detail), status_code=exc.status_code)

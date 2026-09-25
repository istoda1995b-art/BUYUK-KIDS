import os
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase


def _db_url() -> str:
    url = os.getenv("DATABASE_URL")
    if not url:
        # Postgres bo'lmasa — dastavka bazasi (DB_PATH) turgan papkada alohida SQLite fayl
        folder = os.path.dirname(os.path.abspath(os.getenv("DB_PATH", "shop.db")))
        url = f"sqlite+aiosqlite:///{os.path.join(folder, 'kids_site.db')}"
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


DATABASE_URL = _db_url()
engine = create_async_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


class Base(DeclarativeBase):
    pass


async def get_session():
    async with SessionLocal() as s:
        yield s

from datetime import datetime
from sqlalchemy import String, Text, Integer, Boolean, Float, DateTime, LargeBinary, func
from sqlalchemy.orm import Mapped, mapped_column
from .db import Base


class Media(Base):
    """Rasmlar Postgres ichida saqlanadi (Railway diski vaqtinchalik)."""
    __tablename__ = "media"
    id: Mapped[int] = mapped_column(primary_key=True)
    filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(100))
    data: Mapped[bytes] = mapped_column(LargeBinary)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Setting(Base):
    """Kalit-qiymat: sayt matnlari (uz/ru) va umumiy sozlamalar."""
    __tablename__ = "settings"
    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value_uz: Mapped[str] = mapped_column(Text, default="")
    value_ru: Mapped[str] = mapped_column(Text, default="")


class StatCard(Base):
    __tablename__ = "stat_cards"
    id: Mapped[int] = mapped_column(primary_key=True)
    value: Mapped[str] = mapped_column(String(50))
    label_uz: Mapped[str] = mapped_column(String(200))
    label_ru: Mapped[str] = mapped_column(String(200))
    color: Mapped[str] = mapped_column(String(20), default="#2EC4B6")
    icon: Mapped[str] = mapped_column(String(30), default="clock")
    image_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sort: Mapped[int] = mapped_column(Integer, default=0)


class Category(Base):
    __tablename__ = "categories"
    id: Mapped[int] = mapped_column(primary_key=True)
    name_uz: Mapped[str] = mapped_column(String(200))
    name_ru: Mapped[str] = mapped_column(String(200), default="")
    toy: Mapped[str] = mapped_column(String(30), default="bear")
    color: Mapped[str] = mapped_column(String(20), default="#FFF1CC")
    image_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    link: Mapped[str] = mapped_column(String(500), default="")
    sort: Mapped[int] = mapped_column(Integer, default=0)


class Store(Base):
    __tablename__ = "stores"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    address_uz: Mapped[str] = mapped_column(String(300), default="")
    address_ru: Mapped[str] = mapped_column(String(300), default="")
    phone: Mapped[str] = mapped_column(String(50), default="")
    hours: Mapped[str] = mapped_column(String(50), default="09:00 – 23:00")
    rating: Mapped[float] = mapped_column(Float, default=5.0)
    lat: Mapped[float] = mapped_column(Float, default=41.311)
    lon: Mapped[float] = mapped_column(Float, default=69.279)
    image_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort: Mapped[int] = mapped_column(Integer, default=0)


class Post(Base):
    __tablename__ = "posts"
    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    title_uz: Mapped[str] = mapped_column(String(300))
    title_ru: Mapped[str] = mapped_column(String(300))
    excerpt_uz: Mapped[str] = mapped_column(Text, default="")
    excerpt_ru: Mapped[str] = mapped_column(Text, default="")
    body_uz: Mapped[str] = mapped_column(Text, default="")
    body_ru: Mapped[str] = mapped_column(Text, default="")
    image_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_published: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Vacancy(Base):
    __tablename__ = "vacancies"
    id: Mapped[int] = mapped_column(primary_key=True)
    title_uz: Mapped[str] = mapped_column(String(200))
    title_ru: Mapped[str] = mapped_column(String(200))
    desc_uz: Mapped[str] = mapped_column(Text, default="")
    desc_ru: Mapped[str] = mapped_column(Text, default="")
    salary: Mapped[str] = mapped_column(String(100), default="")
    location: Mapped[str] = mapped_column(String(200), default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort: Mapped[int] = mapped_column(Integer, default=0)


class Submission(Base):
    __tablename__ = "submissions"
    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(30))  # contact | partner | career | loyalty
    name: Mapped[str] = mapped_column(String(200))
    phone: Mapped[str] = mapped_column(String(50))
    company: Mapped[str] = mapped_column(String(200), default="")
    subject: Mapped[str] = mapped_column(String(300), default="")
    message: Mapped[str] = mapped_column(Text, default="")
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

LANGS = ("uz", "ru")

UI = {
    "nav_stores": {"uz": "Do'konlar", "ru": "Магазины"},
    "nav_blog": {"uz": "Blog", "ru": "Блог"},
    "nav_about": {"uz": "Kompaniya haqida", "ru": "О компании"},
    "nav_career": {"uz": "Karyera", "ru": "Карьера"},
    "nav_partners": {"uz": "Hamkorlarga", "ru": "Партнерам"},
    "nav_contacts": {"uz": "Kontaktlar", "ru": "Контакты"},
    "nav_loyalty": {"uz": "Keshbek", "ru": "Кэшбэк"},
    "navigation": {"uz": "Navigatsiya", "ru": "Навигация"},
    "contacts": {"uz": "Kontaktlar", "ru": "Контакты"},
    "social": {"uz": "Ijtimoiy tarmoqlar", "ru": "Мы в соцсетях"},
    "rights": {"uz": "Barcha huquqlar himoyalangan.", "ru": "Все права защищены."},
    "to_top": {"uz": "Yuqoriga", "ru": "На главную"},
    "all_posts": {"uz": "Barcha maqolalar", "ru": "Все статьи"},
    "read_more": {"uz": "Batafsil", "ru": "Подробнее"},
    "stores_on_map": {"uz": "Do'konlarimiz xaritada", "ru": "Наши магазины на карте"},
    "open_map": {"uz": "Xaritada ochish", "ru": "Открыть на карте"},
    "search": {"uz": "Qidirish", "ru": "Поиск"},
    "search_ph": {"uz": "Maqola yoki do'kon nomi...", "ru": "Статья или магазин..."},
    "nothing_found": {"uz": "Hech narsa topilmadi", "ru": "Ничего не найдено"},
    "name": {"uz": "Ismingiz", "ru": "Ваше имя"},
    "phone": {"uz": "Telefon raqam", "ru": "Номер телефона"},
    "company": {"uz": "Kompaniya nomi", "ru": "Название компании"},
    "message": {"uz": "Xabar", "ru": "Сообщение"},
    "send": {"uz": "Yuborish", "ru": "Отправить"},
    "sent_ok": {"uz": "Rahmat! Arizangiz qabul qilindi, tez orada bog'lanamiz.",
                "ru": "Спасибо! Заявка принята, мы скоро свяжемся с вами."},
    "vacancies": {"uz": "Ochiq vakansiyalar", "ru": "Открытые вакансии"},
    "no_vacancies": {"uz": "Hozircha ochiq vakansiya yo'q", "ru": "Сейчас открытых вакансий нет"},
    "apply": {"uz": "Ariza topshirish", "ru": "Откликнуться"},
    "position": {"uz": "Lavozim", "ru": "Должность"},
    "leave_request": {"uz": "Ariza qoldiring", "ru": "Оставьте заявку"},
    "write_us": {"uz": "Bizga yozing", "ru": "Напишите нам"},
    "hours": {"uz": "Ish vaqti", "ru": "Время работы"},
    "back": {"uz": "Orqaga", "ru": "Назад"},
    "join_program": {"uz": "Dasturga qo'shilish", "ru": "Присоединиться к программе"},
    "cashback": {"uz": "Keshbek", "ru": "Кэшбэк"},
    "home": {"uz": "Bosh sahifa", "ru": "Главная"},
    "not_found": {"uz": "Sahifa topilmadi", "ru": "Страница не найдена"},
}


def t(key: str, lang: str) -> str:
    item = UI.get(key)
    if not item:
        return key
    return item.get(lang) or item.get("uz") or key


def loc(obj, field: str, lang: str) -> str:
    """obj.title_ru bo'sh bo'lsa, uz ga qaytadi."""
    val = getattr(obj, f"{field}_{lang}", "") or ""
    if not val:
        val = getattr(obj, f"{field}_uz", "") or ""
    return val

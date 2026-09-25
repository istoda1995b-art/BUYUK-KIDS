"""Birinchi ishga tushishda boshlang'ich ma'lumotlar (admin orqali o'zgartiriladi)."""
from sqlalchemy import select, func
from .models import Setting, StatCard, Store, Post, Vacancy, Category

# key: (uz, ru, label, type)  type: text | textarea | image | plain
SETTINGS = {
    # Hero
    "hero_title": ("Buyuk Kids oilasiga qo'shiling", "Станьте частью семьи Buyuk Kids", "Hero: sarlavha", "text"),
    "hero_subtitle": ("Bolangiz uchun hammasi bir joyda — kiyim, o'yinchoq, gigiyena va yana ko'p narsalar. Har bir xariddan bonus to'plang!",
                      "Всё для вашего ребёнка в одном месте — одежда, игрушки, гигиена и многое другое. Копите бонусы с каждой покупки!",
                      "Hero: matn", "textarea"),
    "hero_button": ("Imtiyozlar haqida", "Узнать о привилегиях", "Hero: tugma matni", "text"),
    "hero_image": ("", "", "Hero: fon rasmi (1920x900)", "image"),
    # Buyurtma (dastavka sayti)
    "order_url": ("/shop", "", "Buyurtma havolasi (standart: /shop — shu serverdagi dastavka)", "plain"),
    "order_label": ("Buyurtma berish", "Заказать", "Menyu: buyurtma tugmasi", "text"),
    "delivery_title": ("Uydan chiqmasdan buyurtma bering", "Заказывайте, не выходя из дома", "Dastavka banneri: sarlavha", "text"),
    "delivery_text": ("Kiyim, o'yinchoq va bolalar uchun kerakli barcha narsalarni onlayn buyurtma qiling — eshigingizgacha yetkazib beramiz.",
                      "Заказывайте одежду, игрушки и всё необходимое для детей онлайн — доставим прямо до двери.",
                      "Dastavka banneri: matn", "textarea"),
    # Categories
    "categories_title": ("Bizda nimalar", "Что есть", "Kategoriyalar: sarlavha", "text"),
    "categories_accent": ("bor?", "у нас?", "Kategoriyalar: rangli so'z", "text"),
    # Features
    "features_title": ("Hammasi sizning", "Всё для вашего", "Afzalliklar: sarlavha", "text"),
    "features_accent": ("qulayligingiz uchun", "удобства", "Afzalliklar: rangli so'z", "text"),
    "features_subtitle": ("Farzandlaringizni har kuni xursand qilishingiz uchun eng yaxshi sharoitlarni yaratamiz.",
                          "Создаём лучшие условия, чтобы вы могли радовать своих детей каждый день.",
                          "Afzalliklar: matn", "textarea"),
    # Cashback
    "cashback_percent": ("1%", "1%", "Keshbek foizi", "plain"),
    "cashback_title": ("Keshbek qanday ishlaydi?", "Как работает наш кэшбэк?", "Keshbek: sarlavha", "text"),
    "cashback_text": ("Juda oddiy: har bir xariddan 1% bonus hisobingizga tushadi. To'plangan bonuslar bilan istalgan mahsulotning 100% gacha narxini to'lash mumkin. Kassada telefon raqamingizni ayting!",
                      "Всё просто: получайте 1% с каждой покупки на бонусный счёт. Накопленными бонусами можно оплатить до 100% стоимости любых товаров. Просто назовите свой номер на кассе!",
                      "Keshbek: matn", "textarea"),
    "cashback_button": ("Dasturga qo'shilish", "Присоединиться к программе", "Keshbek: tugma", "text"),
    "loyalty_body": ("1. Kassada telefon raqamingizni ayting yoki quyidagi formani to'ldiring.\n2. Har bir xariddan 1% bonus hisobingizga tushadi.\n3. Bonuslar bilan keyingi xaridlaringizni to'lang — 100% gacha.",
                     "1. Назовите номер телефона на кассе или заполните форму ниже.\n2. С каждой покупки 1% начисляется на бонусный счёт.\n3. Оплачивайте бонусами следующие покупки — до 100%.",
                     "Keshbek sahifasi: shartlar", "textarea"),
    # Blog / stores
    "blog_title": ("Ota-onalar uchun blog", "Блог для родителей", "Blog bo'limi sarlavhasi", "text"),
    "stores_title": ("Bizning do'konlar", "Наши магазины", "Do'konlar bo'limi sarlavhasi", "text"),
    # About
    "about_title": ("Buyuk Kids haqida", "О Buyuk Kids", "Kompaniya: sarlavha", "text"),
    "about_body": ("Buyuk Kids — Buyuk oilasining bolalar supermarketi. Biz 0 yoshdan 14 yoshgacha bo'lgan bolalar uchun sifatli kiyim, o'yinchoqlar, gigiyena va parvarish mahsulotlarini qulay narxlarda taklif qilamiz.\n\nBizning maqsadimiz — ota-onalarning vaqtini tejash va har bir xaridni quvonchli qilish.",
                   "Buyuk Kids — детский супермаркет семьи Buyuk. Мы предлагаем качественную одежду, игрушки, товары для гигиены и ухода для детей от 0 до 14 лет по доступным ценам.\n\nНаша цель — экономить время родителей и делать каждую покупку радостной.",
                   "Kompaniya: matn", "textarea"),
    "about_image": ("", "", "Kompaniya: rasm", "image"),
    "partners_body": ("Buyuk Kids bilan hamkorlik qilishni xohlaysizmi? Biz ishlab chiqaruvchilar, distribyutorlar va ijara takliflari uchun ochiqmiz. Arizangizni qoldiring — mas'ul xodim siz bilan bog'lanadi.",
                      "Хотите сотрудничать с Buyuk Kids? Мы открыты для производителей, дистрибьюторов и предложений по аренде. Оставьте заявку — ответственный сотрудник свяжется с вами.",
                      "Hamkorlarga: matn", "textarea"),
    "career_intro": ("Do'stona jamoamizga qo'shiling! Biz bolalarni va o'z ishini sevadigan insonlarni izlayapmiz.",
                     "Присоединяйтесь к нашей дружной команде! Мы ищем людей, которые любят детей и свою работу.",
                     "Karyera: matn", "textarea"),
    # Footer / contacts
    "footer_about": ("Bolalar uchun supermarket. 0 yoshdan 14 yoshgacha bo'lgan bolalar uchun sifatli kiyim, o'yinchoq va parvarish mahsulotlari.",
                     "Детский супермаркет. Качественная одежда, игрушки и товары для ухода для детей от 0 до 14 лет.",
                     "Footer: qisqa matn", "textarea"),
    "address": ("Toshkent sh.", "г. Ташкент", "Manzil", "text"),
    "email": ("info@buyukkids.uz", "", "Email", "plain"),
    "phone": ("+998 90 000 00 00", "", "Telefon", "plain"),
    "telegram": ("https://t.me/", "", "Telegram havola", "plain"),
    "instagram": ("https://instagram.com/", "", "Instagram havola", "plain"),
    "youtube": ("", "", "YouTube havola", "plain"),
    "facebook": ("", "", "Facebook havola", "plain"),
}

CATEGORIES = [
    ("O'yinchoqlar", "Игрушки", "bear", "#FFE3C2"),
    ("Kiyim-kechak", "Одежда", "tshirt", "#DDF3FF"),
    ("Chaqaloqlar uchun", "Для малышей", "bottle", "#FFE3EA"),
    ("Rivojlantiruvchi", "Развивающие", "pyramid", "#E3F6DC"),
    ("Gigiyena va parvarish", "Гигиена и уход", "cosmetic", "#F3E6FF"),
    ("Maktab uchun", "Для школы", "backpack", "#FFF1CC"),
    ("Aravachalar", "Коляски", "stroller", "#FFE3EA"),
    ("Mashinalar", "Машинки", "car", "#DDF3FF"),
]

STATS = [
    ("9:00 – 23:00", "Qulay ish vaqti", "Удобный график", "#2EC4B6", "clock"),
    ("10 000+", "Mahsulotlar", "Товаров", "#FF6B8B", "box"),
    ("50 000+", "Mamnun ota-onalar", "Довольных родителей", "#FFB400", "heart"),
    ("1", "Do'kon", "Магазин", "#4CB82E", "store"),
]

POSTS = [
    ("bola-uchun-kiyim-tanlash",
     "Bola uchun kiyimni qanday tanlash kerak?", "Как выбрать одежду для ребёнка?",
     "O'lcham, mato va mavsumga qarab to'g'ri tanlov qilish bo'yicha maslahatlar.",
     "Советы по выбору размера, ткани и одежды по сезону.",
     "Bola kiyimini tanlashda eng muhimi — qulaylik. Tabiiy matolar (paxta, zig'ir) terini nafas oldiradi va allergiya xavfini kamaytiradi.\n\nO'lchamni tanlashda bolaning bo'yiga qarang, yoshiga emas: bolalar turlicha o'sadi. Bir o'lcham kattaroq olish — yaxshi fikr, lekin juda katta kiyim harakatga xalaqit beradi.\n\nMavsum almashganda qatlamli kiyinish usulidan foydalaning: yupqa futbolka, kofta va yengil kurtka.",
     "Главное при выборе детской одежды — комфорт. Натуральные ткани (хлопок, лён) дают коже дышать и снижают риск аллергии.\n\nПри выборе размера ориентируйтесь на рост, а не на возраст: дети растут по-разному. Взять на размер больше — хорошая идея, но слишком большая одежда мешает двигаться.\n\nВ межсезонье используйте многослойность: тонкая футболка, кофта и лёгкая куртка."),
    ("rivojlantiruvchi-oyinchoqlar",
     "Qaysi o'yinchoqlar rivojlanishga yordam beradi?", "Какие игрушки помогают развитию?",
     "Yoshga mos rivojlantiruvchi o'yinchoqlar ro'yxati.",
     "Подборка развивающих игрушек по возрасту.",
     "0–1 yosh: shaqildoqlar, yumshoq kubiklar, kontrast rangli kitoblar.\n\n1–3 yosh: piramidalar, saralagichlar, katta konstruktorlar — ular nozik motorikani rivojlantiradi.\n\n3–6 yosh: pazllar, rol o'yinlari to'plamlari, rasm chizish uchun jihozlar.\n\nEng muhimi — o'yinchoq xavfsiz materialdan bo'lishi va bolaning yoshiga mos kelishi.",
     "0–1 год: погремушки, мягкие кубики, контрастные книжки.\n\n1–3 года: пирамидки, сортеры, крупные конструкторы — они развивают мелкую моторику.\n\n3–6 лет: пазлы, наборы для ролевых игр, товары для рисования.\n\nГлавное — игрушка должна быть из безопасных материалов и подходить по возрасту."),
    ("tagliq-tanlash",
     "Chaqaloq uchun tagliqni qanday tanlash kerak?", "Как выбрать подгузник для малыша?",
     "O'lcham, turi va teriga g'amxo'rlik haqida.",
     "О размере, типе и уходе за кожей.",
     "Tagliq o'lchami chaqaloqning vazniga qarab tanlanadi — qadoqdagi jadvalga e'tibor bering.\n\nFaol bolalar uchun tagliq-trusiklar qulayroq: ularni kiydirish oson. Tunda esa yuqori shimuvchan modellarni tanlang.\n\nTeri qizarsa, tagliqni tez-tez almashtiring va maxsus krem ishlating.",
     "Размер подгузника выбирают по весу малыша — ориентируйтесь на таблицу на упаковке.\n\nАктивным детям удобнее трусики: их легко надевать. На ночь выбирайте модели с повышенной впитываемостью.\n\nЕсли кожа покраснела, меняйте подгузник чаще и используйте специальный крем."),
]


async def seed(session):
    existing = {k for (k,) in (await session.execute(select(Setting.key))).all()}
    for key, (uz, ru, _l, _t) in SETTINGS.items():
        if key not in existing:
            session.add(Setting(key=key, value_uz=uz, value_ru=ru))

    if not (await session.execute(select(func.count(StatCard.id)))).scalar():
        for i, (v, lu, lr, c, ic) in enumerate(STATS):
            session.add(StatCard(value=v, label_uz=lu, label_ru=lr, color=c, icon=ic, sort=i))

    if not (await session.execute(select(func.count(Category.id)))).scalar():
        for i, (nu, nr, toy, col) in enumerate(CATEGORIES):
            session.add(Category(name_uz=nu, name_ru=nr, toy=toy, color=col, sort=i))

    if not (await session.execute(select(func.count(Store.id)))).scalar():
        session.add(Store(name="Buyuk Kids", address_uz="Manzilni admin paneldan kiriting",
                          address_ru="Укажите адрес в админ-панели", hours="09:00 – 23:00",
                          rating=5.0, lat=41.311, lon=69.279, phone="+998 90 000 00 00"))

    if not (await session.execute(select(func.count(Post.id)))).scalar():
        for slug, tu, tr, eu, er, bu, br in POSTS:
            session.add(Post(slug=slug, title_uz=tu, title_ru=tr, excerpt_uz=eu, excerpt_ru=er,
                             body_uz=bu, body_ru=br))

    if not (await session.execute(select(func.count(Vacancy.id)))).scalar():
        session.add(Vacancy(title_uz="Sotuvchi-konsultant", title_ru="Продавец-консультант",
                            desc_uz="Mijozlarga maslahat berish, mahsulotlarni joylashtirish. Tajriba shart emas — o'rgatamiz.",
                            desc_ru="Консультирование покупателей, выкладка товара. Опыт не обязателен — обучим.",
                            salary="Kelishiladi", location="Toshkent"))
        session.add(Vacancy(title_uz="Kassir", title_ru="Кассир",
                            desc_uz="Kassada ishlash, mijozlarga xizmat ko'rsatish.",
                            desc_ru="Работа на кассе, обслуживание покупателей.",
                            salary="Kelishiladi", location="Toshkent"))
    await session.commit()

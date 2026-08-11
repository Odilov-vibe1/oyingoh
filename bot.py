import asyncio
import os
import json
import sqlite3
from datetime import datetime, timedelta, timezone
from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, InputMediaPhoto
)
from aiogram.filters import CommandStart, Command
from aiogram.exceptions import TelegramBadRequest
from aiohttp import web

TOKEN = os.environ.get("BOT_TOKEN")
OWNER_ID = int(os.environ.get("OWNER_ID", "0"))

bot = Bot(token=TOKEN)
dp = Dispatcher()

DB_PATH = "/data/bookings.db"
TASHKENT = timezone(timedelta(hours=5))

def now_tj():
    return datetime.now(TASHKENT)

HOURS = [f"{h:02d}:00" for h in range(5, 23)]
STATE = {}
ADMIN_STATE = {}
NEWFIELD_STATE = {}
ASSIGN_STATE = {}
EDIT_STATE = {}

VILOYATLAR = {
    "Qoraqalpog'iston Respublikasi": ["Nukus shahri","Amudaryo","Beruniy","Kegeyli","Qonliko'l","Qorao'zak","Qo'ng'irot","Mo'ynoq","Nukus tumani","Taxiatosh","Taxtako'pir","To'rtko'l","Xo'jayli","Chimboy","Sho'manoy","Ellikqal'a"],
    "Andijon viloyati": ["Andijon shahri","Xonabod shahri","Andijon tumani","Asaka","Baliqchi","Bo'z","Buloqboshi","Jalaquduq","Izboskan","Qo'rg'ontepa","Marhamat","Oltinko'l","Paxtaobod","Ulug'nor","Xo'jaobod","Shahrixon"],
    "Buxoro viloyati": ["Buxoro shahri","Kogon shahri","Buxoro tumani","Vobkent","Jondor","Kogon tumani","Olot","Peshku","Romitan","Shofirkon","Qorovulbozor","Qorako'l","G'ijduvon"],
    "Jizzax viloyati": ["Jizzax shahri","Arnasoy","Baxmal","Do'stlik","Zarbdor","Zafarobod","Zomin","Mirzacho'l","Paxtakor","Forish","Sharof Rashidov","G'allaorol","Yangiobod"],
    "Qashqadaryo viloyati": ["Qarshi shahri","Shahrisabz shahri","Dehqonobod","Kasbi","Kitob","Koson","Mirishkor","Muborak","Nishon","Chiroqchi","Shahrisabz tumani","Yakkabog'","Qamashi","Qarshi tumani","G'uzor"],
    "Navoiy viloyati": ["Navoiy shahri","Zarafshon shahri","Karmana","Konimex","Navbahor","Nurota","Tomdi","Uchquduq","Xatirchi","Qiziltepa"],
    "Namangan viloyati": ["Namangan shahri","Kosonsoy","Mingbuloq","Namangan tumani","Norin","Pop","To'raqo'rg'on","Uychi","Uchqo'rg'on","Chortoq","Chust","Yangiqo'rg'on"],
    "Samarqand viloyati": ["Samarqand shahri","Kattaqo'rg'on shahri","Bulung'ur","Jomboy","Ishtixon","Kattaqo'rg'on tumani","Narpay","Nurobod","Oqdaryo","Payariq","Pastdarg'om","Paxtachi","Samarqand tumani","Toyloq","Urgut","Qo'shrabot"],
    "Surxondaryo viloyati": ["Termiz shahri","Angor","Boysun","Denov","Jarqo'rg'on","Muzrobod","Oltinsoy","Sariosiyo","Termiz tumani","Uzun","Sherobod","Sho'rchi","Qiziriq","Qumqo'rg'on","Bandixon"],
    "Sirdaryo viloyati": ["Guliston shahri","Yangiyer shahri","Shirin shahri","Boyovut","Guliston tumani","Mirzaobod","Oqoltin","Sardoba","Sayxunobod","Sirdaryo tumani","Xovos"],
    "Toshkent viloyati": ["Nurafshon shahri","Angren shahri","Bekobod shahri","Olmaliq shahri","Ohangaron shahri","Chirchiq shahri","Yangiyo'l shahri","Bekobod tumani","Bo'ka","Bo'stonliq","Zangiota","Qibray","Quyichirchiq","Oqqo'rg'on","Ohangaron tumani","Parkent","Piskent","Toshkent tumani","O'rtachirchiq","Chinoz","Yuqorichirchiq","Yangiyo'l tumani"],
    "Farg'ona viloyati": ["Farg'ona shahri","Marg'ilon shahri","Quvasoy shahri","Qo'qon shahri","Beshariq","Bog'dod","Buvayda","Dang'ara","Yozyovon","Quva","Qo'shtepa","Oltiariq","Rishton","So'x","Toshloq","O'zbekiston","Uchko'prik","Farg'ona tumani","Furqat"],
    "Xorazm viloyati": ["Urganch shahri","Xiva shahri","Bog'ot","Gurlan","Urganch tumani","Xiva tumani","Xonqa","Hazorasp","Shovot","Yangiariq","Yangibozor","Qo'shko'pir","Tuproqqal'a"],
    "Toshkent shahri": ["Bektemir","Mirzo Ulug'bek","Mirobod","Olmazor","Sirg'ali","Uchtepa","Chilonzor","Shayxontohur","Yunusobod","Yakkasaroy","Yashnobod","Yangihayot"],
}
VILOYAT_LIST = list(VILOYATLAR.keys())

def db():
    return sqlite3.connect(DB_PATH)

async def safe_edit(callback: CallbackQuery, text: str, keyboard=None):
    try:
        await callback.message.edit_text(text, reply_markup=keyboard)
    except TelegramBadRequest:
        pass
    await callback.answer()

def admin_menu_keyboard():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="📋 Bronlar"), KeyboardButton(text="➕ Bron qo'shish")],
        [KeyboardButton(text="📊 Statistika"), KeyboardButton(text="🧑‍💼 Admin tayinlash")],
        [KeyboardButton(text="🗑 Maydonlarni boshqarish")]
    ], resize_keyboard=True)

def customer_menu_keyboard():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="⚽ Bron qilish")],
        [KeyboardButton(text="📋 Mening bronlarim")],
        [KeyboardButton(text="🏟 Gazon egasiman")]
    ], resize_keyboard=True)

def owner_menu_keyboard():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="📅 Mening maydonlarim bronlari"), KeyboardButton(text="➕ Bron qo'shish")],
        [KeyboardButton(text="✏️ Maydonlarni tahrirlash")],
        [KeyboardButton(text="🏟 Gazon egasiman")],
        [KeyboardButton(text="⚽ Bron qilish")]
    ], resize_keyboard=True)

def viloyat_keyboard():
    buttons, row = [], []
    for i, v in enumerate(VILOYAT_LIST):
        row.append(InlineKeyboardButton(text=v, callback_data=f"geov|{i}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def tuman_keyboard(vidx):
    tumanlar = VILOYATLAR[VILOYAT_LIST[vidx]]
    buttons, row = [], []
    for i, t in enumerate(tumanlar):
        row.append(InlineKeyboardButton(text=t, callback_data=f"geot|{vidx}|{i}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="geoback")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

OFFER_TEXT = (
    "📄 Hamkorlik shartlari (oferta)\n\n"
    "1. O'yingoh — sport maydonlarini bron qilish uchun Telegram-bot xizmati.\n"
    "2. Siz maydon haqida to'g'ri ma'lumot (narx, manzil, vaqt) berishga majbursiz.\n"
    "3. Hozircha xizmat bepul. Kelajakda haq joriy etilsa, oldindan xabar beriladi.\n"
    "4. Bot orqali kelgan bronlarni hurmat qiling.\n"
    "5. Mijoz ismi/raqami faqat bog'lanish uchun ishlatiladi.\n"
    "6. Istalgan vaqt hamkorlikni bekor qilishingiz mumkin.\n\n"
    "Roziligingizni bildirish uchun pastga \"Roziman\" deb yozing:"
)

def init_db():
    conn = db()
    conn.execute("CREATE TABLE IF NOT EXISTS bookings (id INTEGER PRIMARY KEY AUTOINCREMENT, region TEXT, field TEXT, date TEXT, time TEXT, user_id INTEGER, user_name TEXT, phone TEXT)")
    conn.execute("CREATE TABLE IF NOT EXISTS users (telegram_id INTEGER PRIMARY KEY, phone TEXT, full_name TEXT)")
    conn.execute("CREATE TABLE IF NOT EXISTS fields (id TEXT PRIMARY KEY, region TEXT, name TEXT, price TEXT, emoji TEXT, location TEXT, owner_id INTEGER, status TEXT DEFAULT 'pending')")
    for stmt in [
        "ALTER TABLE bookings ADD COLUMN phone TEXT",
        "ALTER TABLE bookings ADD COLUMN reminded INTEGER DEFAULT 0",
        "ALTER TABLE users ADD COLUMN full_name TEXT",
        "ALTER TABLE fields ADD COLUMN owner_phone TEXT",
        "ALTER TABLE fields ADD COLUMN offer_accepted TEXT",
        "ALTER TABLE fields ADD COLUMN photo_id TEXT",
    ]:
        try:
            conn.execute(stmt)
        except sqlite3.OperationalError:
            pass
    conn.commit()
    conn.close()

def get_field(field_id):
    conn = db()
    row = conn.execute("SELECT id,region,name,price,emoji,location,owner_id,status,owner_phone,photo_id FROM fields WHERE id=?", (field_id,)).fetchone()
    conn.close()
    return row

def get_approved_fields():
    conn = db()
    rows = conn.execute("SELECT id,region,name,price,emoji,location,owner_id FROM fields WHERE status='approved' ORDER BY region, name").fetchall()
    conn.close()
    return rows

def get_owned_fields(user_id):
    conn = db()
    rows = conn.execute("SELECT id,region,name,price,emoji,location,owner_id FROM fields WHERE owner_id=? AND status='approved' ORDER BY name", (user_id,)).fetchall()
    conn.close()
    return rows

def get_all_fields():
    conn = db()
    rows = conn.execute("SELECT id,region,name,price,emoji,location,owner_id,status FROM fields ORDER BY status DESC, region, name").fetchall()
    conn.close()
    return rows

def get_regions():
    regions = {}
    for f in get_approved_fields():
        regions.setdefault(f[1], []).append(f)
    return regions

def can_manage(user_id, field_id):
    if user_id == OWNER_ID:
        return True
    f = get_field(field_id)
    return bool(f and f[6] == user_id)

def get_photos(raw):
    if not raw:
        return []
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            return data
        return [raw]
    except Exception:
        return [raw]

def add_photo(field_id, file_id):
    f = get_field(field_id)
    photos = get_photos(f[9]) if f else []
    if len(photos) >= 4:
        return False
    photos.append(file_id)
    conn = db()
    conn.execute("UPDATE fields SET photo_id=? WHERE id=?", (json.dumps(photos), field_id))
    conn.commit()
    conn.close()
    return True

def get_user_info(user_id):
    conn = db()
    row = conn.execute("SELECT phone, full_name FROM users WHERE telegram_id=?", (user_id,)).fetchone()
    conn.close()
    return (row[0], row[1]) if row else (None, None)

def save_user_info(user_id, phone, full_name):
    conn = db()
    conn.execute("INSERT OR REPLACE INTO users (telegram_id, phone, full_name) VALUES (?,?,?)", (user_id, phone, full_name))
    conn.commit()
    conn.close()

def get_booked_times(field_id, date):
    conn = db()
    rows = [r[0] for r in conn.execute("SELECT time FROM bookings WHERE field=? AND date=?", (field_id, date)).fetchall()]
    conn.close()
    return rows

def add_booking(field_id, date, time, user_id, user_name, phone):
    conn = db()
    conn.execute("INSERT INTO bookings (field, date, time, user_id, user_name, phone) VALUES (?,?,?,?,?,?)", (field_id, date, time, user_id, user_name, phone))
    conn.commit()
    conn.close()

def get_upcoming_bookings():
    today = now_tj().strftime("%Y-%m-%d")
    conn = db()
    rows = conn.execute(
        "SELECT b.id, b.field, b.date, b.time, b.user_name, b.user_id, b.phone, f.name, f.emoji "
        "FROM bookings b LEFT JOIN fields f ON b.field=f.id WHERE b.date>=? ORDER BY b.date, b.time", (today,)
    ).fetchall()
    conn.close()
    return rows

def get_owner_bookings(user_id):
    today = now_tj().strftime("%Y-%m-%d")
    conn = db()
    rows = conn.execute(
        "SELECT b.id, b.field, b.date, b.time, b.user_name, b.user_id, b.phone, f.name, f.emoji "
        "FROM bookings b LEFT JOIN fields f ON b.field=f.id WHERE f.owner_id=? AND b.date>=? ORDER BY b.date, b.time", (user_id, today)
    ).fetchall()
    conn.close()
    return rows

def get_user_bookings(user_id):
    today = now_tj().strftime("%Y-%m-%d")
    conn = db()
    rows = conn.execute(
        "SELECT b.id, b.field, b.date, b.time, f.name, f.emoji FROM bookings b LEFT JOIN fields f ON b.field=f.id "
        "WHERE b.user_id=? AND b.date>=? ORDER BY b.date, b.time", (user_id, today)
    ).fetchall()
    conn.close()
    return rows

def get_booking(booking_id):
    conn = db()
    row = conn.execute("SELECT field, date, time, user_id, user_name FROM bookings WHERE id=?", (booking_id,)).fetchone()
    conn.close()
    return row

def delete_booking(booking_id):
    conn = db()
    conn.execute("DELETE FROM bookings WHERE id=?", (booking_id,))
    conn.commit()
    conn.close()

def delete_field(field_id):
    conn = db()
    conn.execute("DELETE FROM fields WHERE id=?", (field_id,))
    conn.commit()
    conn.close()

def get_stats():
    conn = db()
    total = conn.execute("SELECT COUNT(*) FROM bookings").fetchone()[0]
    today = now_tj().strftime("%Y-%m-%d")
    week_end = (now_tj() + timedelta(days=7)).strftime("%Y-%m-%d")
    today_count = conn.execute("SELECT COUNT(*) FROM bookings WHERE date=?", (today,)).fetchone()[0]
    week_count = conn.execute("SELECT COUNT(*) FROM bookings WHERE date>=? AND date<=?", (today, week_end)).fetchone()[0]
    per_field = conn.execute(
        "SELECT b.field, COUNT(*) c, f.name, f.emoji FROM bookings b LEFT JOIN fields f ON b.field=f.id GROUP BY b.field ORDER BY c DESC"
    ).fetchall()
    busiest = conn.execute("SELECT time, COUNT(*) c FROM bookings GROUP BY time ORDER BY c DESC LIMIT 1").fetchone()
    conn.close()
    return total, today_count, week_count, per_field, busiest

def region_menu():
    regions = get_regions()
    buttons = [[InlineKeyboardButton(text=f"📍 {r}", callback_data=f"region|{r}")] for r in regions.keys()]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def field_menu(region_name):
    fields = [f for f in get_approved_fields() if f[1] == region_name]
    buttons = [[InlineKeyboardButton(text=f"{f[4]} {f[2]} — {f[3]} so'm", callback_data=f"field|{f[0]}")] for f in fields]
    if not buttons:
        buttons = [[InlineKeyboardButton(text="Hozircha maydon yo'q", callback_data="taken")]]
    elif len(fields) >= 2:
        buttons.append([InlineKeyboardButton(text="🆚 Taqqoslash", callback_data=f"compare|{region_name}")])
    buttons.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_regions")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def day_menu(field_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📅 Bugun", callback_data=f"day|{field_id}|0")],
        [InlineKeyboardButton(text="🗓 Boshqa kun", callback_data=f"days|{field_id}")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_regions")],
    ])

def days_list(field_id):
    buttons = []
    for i in range(7):
        d = now_tj() + timedelta(days=i)
        buttons.append([InlineKeyboardButton(text=d.strftime("%d-%m"), callback_data=f"day|{field_id}|{i}")])
    buttons.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data=f"field|{field_id}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def slots_menu(field_id, date_str, prefix="book"):
    booked = get_booked_times(field_id, date_str)
    now = now_tj()
    is_today = date_str == now.strftime("%Y-%m-%d")
    buttons, row = [], []
    for h in HOURS:
        is_past = is_today and int(h.split(":")[0]) <= now.hour
        if h in booked:
            row.append(InlineKeyboardButton(text=f"🔴 {h}", callback_data="taken"))
        elif is_past:
            row.append(InlineKeyboardButton(text=f"🟡 {h}", callback_data="taken"))
        else:
            row.append(InlineKeyboardButton(text=f"🟢 {h}", callback_data=f"{prefix}|{field_id}|{date_str}|{h}"))
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    back_cb = f"field|{field_id}" if prefix == "book" else f"aday|{field_id}"
    buttons.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data=back_cb)])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def phone_request_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Raqamni ulashish", request_contact=True)]],
        resize_keyboard=True, one_time_keyboard=True
    )

def get_forward_user_id(message: Message):
    origin = getattr(message, "forward_origin", None)
    if origin is not None:
        sender_user = getattr(origin, "sender_user", None)
        if sender_user:
            return sender_user.id
        return None
    if message.forward_from:
        return message.forward_from.id
    return None

def is_forwarded(message: Message):
    return bool(getattr(message, "forward_origin", None) or message.forward_from or message.forward_sender_name)

async def finalize_booking(field_id, date_str, time_str, user_id, full_name, username, phone):
    add_booking(field_id, date_str, time_str, user_id, full_name, phone)
    f = get_field(field_id)
    await bot.send_message(
        user_id,
        f"✅ Bron qilindi!\n\n{f[4]} {f[2]}\n📅 {date_str}\n🕐 {time_str}\n\nTez orada siz bilan bog'lanishadi."
    )
    notify_ids = set()
    if f and f[6]:
        notify_ids.add(f[6])
    if OWNER_ID:
        notify_ids.add(OWNER_ID)
    for nid in notify_ids:
        try:
            await bot.send_message(
                nid,
                f"🔔 Yangi bron!\n\n{f[4]} {f[2]}\n📅 {date_str}  🕐 {time_str}\n👤 {full_name} (@{username or 'yoq'})\n📞 {phone}"
            )
        except Exception:
            pass

async def start_info_flow(user_id, pending):
    STATE[user_id] = {"step": "name", "pending": pending}
    await bot.send_message(user_id, "✍️ Bronni tasdiqlash uchun ism va familiyangizni to'liq yozing\n(masalan: Aliyev Vali):")

@dp.message(CommandStart())
async def start(message: Message):
    user_id = message.from_user.id
    STATE.pop(user_id, None)
    ADMIN_STATE.pop(user_id, None)
    NEWFIELD_STATE.pop(user_id, None)
    ASSIGN_STATE.pop(user_id, None)
    EDIT_STATE.pop(user_id, None)
    if user_id == OWNER_ID:
        await message.answer("👨‍💼 Bosh menejer paneliga xush kelibsiz!\n\nQuyidagi tugmalardan foydalaning:", reply_markup=admin_menu_keyboard())
        return
    owned = get_owned_fields(user_id)
    if owned:
        await message.answer(
            f"👨‍💼 Xush kelibsiz! Sizda {len(owned)} ta faol maydon bor.\n\nQuyidagi tugmalardan foydalaning:",
            reply_markup=owner_menu_keyboard()
        )
        return
    await message.answer(
        f"⚽ Xush kelibsiz, {message.from_user.first_name}!\n\n🏟 O'yingoh — maydon bron qilish boti!",
        reply_markup=customer_menu_keyboard()
    )

@dp.message(F.text == "⚽ Bron qilish")
async def btn_book(message: Message):
    if message.from_user.id == OWNER_ID:
        return
    STATE.pop(message.from_user.id, None)
    regions = get_regions()
    if not regions:
        await message.answer("Hozircha faol maydon yo'q.")
        return
    await message.answer("Hududni tanlang:", reply_markup=region_menu())

@dp.message(F.text == "📋 Mening bronlarim")
async def btn_my_bookings(message: Message):
    if message.from_user.id == OWNER_ID:
        return
    rows = get_user_bookings(message.from_user.id)
    if not rows:
        await message.answer("📋 Sizda hozircha aktiv bron yo'q.")
        return
    await message.answer(f"📋 Sizning aktiv bronlaringiz ({len(rows)} ta):")
    for r in rows:
        booking_id, field_id, date, time, fname, femoji = r
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"mycancel|{booking_id}")]
        ])
        await message.answer(f"{femoji} {fname}\n📅 {date}  🕐 {time}", reply_markup=keyboard)

@dp.message(F.text == "📅 Mening maydonlarim bronlari")
async def btn_owner_bookings(message: Message):
    user_id = message.from_user.id
    if user_id == OWNER_ID:
        return
    rows = get_owner_bookings(user_id)
    if not rows:
        await message.answer("📋 Hozircha aktiv bronlar yo'q.")
        return
    await message.answer(f"📋 Jami {len(rows)} ta aktiv bron:")
    for r in rows:
        booking_id, field_id, date, time, uname, uid, phone, fname, femoji = r
        phone_line = f"\n📞 {phone}" if phone else ""
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"cancel|{booking_id}")]
        ])
        await message.answer(f"{femoji} {fname}\n📅 {date}  🕐 {time}\n👤 {uname}{phone_line}", reply_markup=keyboard)

@dp.message(F.text == "🏟 Gazon egasiman")
async def btn_add_field(message: Message):
    NEWFIELD_STATE[message.from_user.id] = {"step": "viloyat"}
    await message.answer("🏟 Yangi maydon qo'shish\n\nViloyatni tanlang:", reply_markup=viloyat_keyboard())

@dp.callback_query(F.data.startswith("geov|"))
async def geo_viloyat(callback: CallbackQuery):
    if callback.from_user.id not in NEWFIELD_STATE:
        await callback.answer()
        return
    vidx = int(callback.data.split("|")[1])
    viloyat = VILOYAT_LIST[vidx]
    NEWFIELD_STATE[callback.from_user.id]["viloyat"] = viloyat
    NEWFIELD_STATE[callback.from_user.id]["step"] = "tuman"
    await safe_edit(callback, f"📍 {viloyat}\n\nTumanni tanlang:", tuman_keyboard(vidx))

@dp.callback_query(F.data == "geoback")
async def geo_back(callback: CallbackQuery):
    if callback.from_user.id not in NEWFIELD_STATE:
        await callback.answer()
        return
    NEWFIELD_STATE[callback.from_user.id]["step"] = "viloyat"
    await safe_edit(callback, "Viloyatni tanlang:", viloyat_keyboard())

@dp.callback_query(F.data.startswith("geot|"))
async def geo_tuman(callback: CallbackQuery):
    if callback.from_user.id not in NEWFIELD_STATE:
        await callback.answer()
        return
    _, vidx, tidx = callback.data.split("|")
    viloyat = VILOYAT_LIST[int(vidx)]
    tuman = VILOYATLAR[viloyat][int(tidx)]
    st = NEWFIELD_STATE[callback.from_user.id]
    st["viloyat"] = viloyat
    st["tuman"] = tuman
    st["region"] = f"{tuman}, {viloyat}"
    st["step"] = "location"
    try:
        await callback.message.edit_text(f"📍 {tuman}, {viloyat}\n\nQishloq/mahalla va aniq manzilni yozing\n(masalan: Guliston MFY, markaziy maydon yonida):")
    except TelegramBadRequest:
        pass
    await callback.answer()

@dp.message(F.photo, F.func(lambda m: m.from_user.id in NEWFIELD_STATE and NEWFIELD_STATE.get(m.from_user.id, {}).get("step") == "photo"))
async def newfield_photo(message: Message):
    st = NEWFIELD_STATE[message.from_user.id]
    st["photo_id"] = message.photo[-1].file_id
    st["step"] = "offer"
    await message.answer(OFFER_TEXT)

@dp.message(F.text, F.func(lambda m: m.from_user.id in NEWFIELD_STATE and not m.text.startswith("/")))
async def newfield_flow(message: Message):
    st = NEWFIELD_STATE[message.from_user.id]
    if st["step"] == "location":
        st["location"] = message.text.strip()
        st["step"] = "name"
        await message.answer("Maydon nomini yozing (masalan: Katta Futbol Maydoni):")
    elif st["step"] == "name":
        st["name"] = message.text.strip()
        st["step"] = "price"
        await message.answer("1 soat narxini yozing (faqat raqam, masalan: 100000):")
    elif st["step"] == "price":
        digits = "".join(c for c in message.text if c.isdigit())
        if not digits:
            await message.answer("Iltimos, narxni raqamda yozing.")
            return
        st["price"] = f"{int(digits):,}".replace(",", " ")
        st["step"] = "phone"
        await message.answer(
            "📞 Siz bilan bog'lanish uchun telefon raqamingizni yozing\n(masalan: +998901234567)\n\nyoki pastdagi tugma orqali ulashing:",
            reply_markup=phone_request_keyboard()
        )
    elif st["step"] == "phone":
        digits = "".join(c for c in message.text if c.isdigit())
        if len(digits) < 7:
            await message.answer("Iltimos, to'g'ri telefon raqam kiriting.")
            return
        st["phone"] = message.text.strip()
        st["step"] = "photo"
        await message.answer(
            "📸 Maydon rasmini yuboring (bitta foto)\n\nAgar hozircha rasm bo'lmasa, \"o'tkazib yuborish\" deb yozing:",
            reply_markup=ReplyKeyboardRemove()
        )
    elif st["step"] == "photo":
        if "o'tkaz" in message.text.strip().lower():
            st["step"] = "offer"
            await message.answer(OFFER_TEXT)
        else:
            await message.answer("Iltimos, rasm yuboring yoki \"o'tkazib yuborish\" deb yozing.")
    elif st["step"] == "offer":
        if message.text.strip().lower() != "roziman":
            await message.answer("Davom etish uchun aniq \"Roziman\" deb yozing.")
            return
        field_id = f"f{int(datetime.now().timestamp())}"
        photo_id = st.get("photo_id")
        photo_json = json.dumps([photo_id]) if photo_id else None
        conn = db()
        conn.execute(
            "INSERT INTO fields (id,region,name,price,emoji,location,owner_id,status,owner_phone,offer_accepted,photo_id) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (field_id, st["region"], st["name"], st["price"], "🏟", st["location"], message.from_user.id, "pending", st["phone"], now_tj().strftime("%Y-%m-%d %H:%M"), photo_json)
        )
        conn.commit()
        conn.close()
        NEWFIELD_STATE.pop(message.from_user.id, None)
        await message.answer("✅ Arizangiz yuborildi! Tez orada siz bilan bog'lanib, ma'lumotlarni tasdiqlaymiz.", reply_markup=customer_menu_keyboard())
        if OWNER_ID:
            kb = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"fapprove|{field_id}"),
                InlineKeyboardButton(text="❌ Rad etish", callback_data=f"freject|{field_id}")
            ]])
            caption = f"🆕 Yangi maydon so'rovi:\n\n📍 {st['region']}\n📌 {st['location']}\n🏟 {st['name']}\n💰 {st['price']} so'm/soat\n📞 Egasi raqami: {st['phone']}\n👤 @{message.from_user.username or message.from_user.first_name}\n\n⚠️ Tasdiqlashdan oldin raqamiga qo'ng'iroq qilib tekshiring!"
            try:
                if photo_id:
                    await bot.send_photo(OWNER_ID, photo=photo_id, caption=caption, reply_markup=kb)
                else:
                    await bot.send_message(OWNER_ID, caption, reply_markup=kb)
            except Exception:
                pass

@dp.message(F.text == "✏️ Maydonlarni tahrirlash")
async def btn_edit_fields(message: Message):
    user_id = message.from_user.id
    if user_id == OWNER_ID:
        return
    fields = get_owned_fields(user_id)
    if not fields:
        await message.answer("Sizda hozircha faol maydon yo'q.")
        return
    buttons = [[InlineKeyboardButton(text=f"{f[4]} {f[2]}", callback_data=f"editf|{f[0]}")] for f in fields]
    await message.answer("Qaysi maydonni tahrirlaysiz?", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

@dp.callback_query(F.data.startswith("editf|"))
async def edit_field_menu(callback: CallbackQuery):
    field_id = callback.data.split("|")[1]
    if not can_manage(callback.from_user.id, field_id):
        await callback.answer("Ruxsat yo'q", show_alert=True)
        return
    f = get_field(field_id)
    photos_count = len(get_photos(f[9]))
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Narxni o'zgartirish", callback_data=f"editprice|{field_id}")],
        [InlineKeyboardButton(text="📌 Manzilni o'zgartirish", callback_data=f"editloc|{field_id}")],
        [InlineKeyboardButton(text=f"📸 Rasm qo'shish ({photos_count}/4)", callback_data=f"editphoto|{field_id}")],
    ])
    await safe_edit(callback, f"{f[4]} {f[2]}\n💰 {f[3]} so'm\n📌 {f[5]}\n\nNimani tahrirlaysiz?", kb)

@dp.callback_query(F.data.startswith("editprice|"))
async def edit_price_start(callback: CallbackQuery):
    field_id = callback.data.split("|")[1]
    if not can_manage(callback.from_user.id, field_id):
        await callback.answer("Ruxsat yo'q", show_alert=True)
        return
    EDIT_STATE[callback.from_user.id] = {"field": field_id, "type": "price"}
    await callback.message.answer("Yangi narxni yozing (faqat raqam, masalan: 150000):")
    await callback.answer()

@dp.callback_query(F.data.startswith("editloc|"))
async def edit_loc_start(callback: CallbackQuery):
    field_id = callback.data.split("|")[1]
    if not can_manage(callback.from_user.id, field_id):
        await callback.answer("Ruxsat yo'q", show_alert=True)
        return
    EDIT_STATE[callback.from_user.id] = {"field": field_id, "type": "location"}
    await callback.message.answer("Yangi manzilni yozing:")
    await callback.answer()

@dp.callback_query(F.data.startswith("editphoto|"))
async def edit_photo_start(callback: CallbackQuery):
    field_id = callback.data.split("|")[1]
    if not can_manage(callback.from_user.id, field_id):
        await callback.answer("Ruxsat yo'q", show_alert=True)
        return
    f = get_field(field_id)
    if len(get_photos(f[9])) >= 4:
        await callback.answer("Maksimal 4 ta rasm, avval birortasini olib tashlang", show_alert=True)
        return
    EDIT_STATE[callback.from_user.id] = {"field": field_id, "type": "photo"}
    await callback.message.answer("Yangi rasmni yuboring:")
    await callback.answer()

@dp.message(F.text, F.func(lambda m: m.from_user.id in EDIT_STATE and EDIT_STATE.get(m.from_user.id, {}).get("type") in ("price", "location") and not m.text.startswith("/")))
async def edit_text_handler(message: Message):
    st = EDIT_STATE.pop(message.from_user.id)
    field_id = st["field"]
    if not can_manage(message.from_user.id, field_id):
        return
    if st["type"] == "price":
        digits = "".join(c for c in message.text if c.isdigit())
        if not digits:
            await message.answer("Iltimos, raqam kiriting.")
            EDIT_STATE[message.from_user.id] = st
            return
        new_price = f"{int(digits):,}".replace(",", " ")
        conn = db()
        conn.execute("UPDATE fields SET price=? WHERE id=?", (new_price, field_id))
        conn.commit()
        conn.close()
        await message.answer(f"✅ Narx yangilandi: {new_price} so'm")
    elif st["type"] == "location":
        conn = db()
        conn.execute("UPDATE fields SET location=? WHERE id=?", (message.text.strip(), field_id))
        conn.commit()
        conn.close()
        await message.answer("✅ Manzil yangilandi.")

@dp.message(F.photo, F.func(lambda m: m.from_user.id in EDIT_STATE and EDIT_STATE.get(m.from_user.id, {}).get("type") == "photo"))
async def edit_photo_receive(message: Message):
    st = EDIT_STATE.pop(message.from_user.id)
    field_id = st["field"]
    if not can_manage(message.from_user.id, field_id):
        return
    ok = add_photo(field_id, message.photo[-1].file_id)
    await message.answer("✅ Rasm qo'shildi." if ok else "Maksimal 4 ta rasm chegarasiga yetdingiz.")

@dp.message(F.contact)
async def contact_received(message: Message):
    user_id = message.from_user.id

    nf = NEWFIELD_STATE.get(user_id)
    if nf and nf.get("step") == "phone":
        nf["phone"] = message.contact.phone_number
        nf["step"] = "photo"
        await message.answer(
            "📸 Maydon rasmini yuboring (bitta foto)\n\nAgar hozircha rasm bo'lmasa, \"o'tkazib yuborish\" deb yozing:",
            reply_markup=ReplyKeyboardRemove()
        )
        return

    st = STATE.get(user_id)
    if not st or st["step"] != "phone":
        return
    if not message.contact or message.contact.user_id != user_id:
        await message.answer("Iltimos, faqat o'z raqamingizni yuboring.")
        return
    phone = message.contact.phone_number
    full_name = st["name"]
    field_id, date_str, time_str = st["pending"]
    STATE.pop(user_id, None)
    save_user_info(user_id, phone, full_name)
    await message.answer("Rahmat!", reply_markup=customer_menu_keyboard())
    if time_str in get_booked_times(field_id, date_str):
        await message.answer("Kechirasiz, navbatingizda ushbu vaqt band bo'lib qoldi. Qaytadan urinib ko'ring.")
        return
    await finalize_booking(field_id, date_str, time_str, user_id, full_name, message.from_user.username, phone)

@dp.callback_query(F.data.startswith("fapprove|"))
async def field_approve(callback: CallbackQuery):
    if callback.from_user.id != OWNER_ID:
        await callback.answer("Ruxsat yo'q", show_alert=True)
        return
    field_id = callback.data.split("|")[1]
    conn = db()
    conn.execute("UPDATE fields SET status='approved' WHERE id=?", (field_id,))
    conn.commit()
    conn.close()
    f = get_field(field_id)
    try:
        await callback.message.edit_caption(caption=f"✅ Tasdiqlandi: {f[2] if f else field_id}")
    except (TelegramBadRequest, TypeError):
        try:
            await callback.message.edit_text(f"✅ Tasdiqlandi: {f[2] if f else field_id}")
        except TelegramBadRequest:
            pass
    await callback.answer()
    if f and f[6]:
        try:
            await bot.send_message(f[6], f"🎉 Tabriklaymiz! \"{f[2]}\" maydoningiz tasdiqlandi va botda faol bo'ldi.\n\nEndi botga /start yozing — sizga maxsus boshqaruv paneli ochiladi.")
        except Exception:
            pass

@dp.callback_query(F.data.startswith("freject|"))
async def field_reject(callback: CallbackQuery):
    if callback.from_user.id != OWNER_ID:
        await callback.answer("Ruxsat yo'q", show_alert=True)
        return
    field_id = callback.data.split("|")[1]
    f = get_field(field_id)
    delete_field(field_id)
    try:
        await callback.message.edit_caption(caption="❌ Rad etildi.")
    except (TelegramBadRequest, TypeError):
        try:
            await callback.message.edit_text("❌ Rad etildi.")
        except TelegramBadRequest:
            pass
    await callback.answer()
    if f and f[6]:
        try:
            await bot.send_message(f[6], f"Kechirasiz, \"{f[2]}\" maydoningiz tasdiqlanmadi.")
        except Exception:
            pass

@dp.callback_query(F.data.startswith("mycancel|"))
async def my_cancel_booking(callback: CallbackQuery):
    booking_id = int(callback.data.split("|")[1])
    booking = get_booking(booking_id)
    if not booking:
        await callback.answer("Bu bron allaqachon bekor qilingan", show_alert=True)
        return
    field_id, date, time, user_id, user_name = booking
    if callback.from_user.id != user_id:
        await callback.answer("Bu sizning broningiz emas", show_alert=True)
        return
    f = get_field(field_id)
    delete_booking(booking_id)
    await callback.message.edit_text(f"❌ Bron bekor qilindi:\n{f[4]} {f[2]}\n📅 {date} 🕐 {time}")
    await callback.answer()
    if f and f[6]:
        try:
            await bot.send_message(f[6], f"⚠️ Mijoz bronni bekor qildi:\n\n{f[4]} {f[2]}\n📅 {date}  🕐 {time}\n👤 {user_name}")
        except Exception:
            pass

@dp.message(Command("stats"))
async def stats_command(message: Message):
    if message.from_user.id != OWNER_ID:
        return
    total, today_count, week_count, per_field, busiest = get_stats()
    text = "📊 Statistika\n\n"
    text += f"Jami bronlar: {total}\n"
    text += f"Bugun: {today_count}\n"
    text += f"Shu hafta: {week_count}\n\n"
    if per_field:
        text += "Maydon bo'yicha:\n"
        for field_id, count, fname, femoji in per_field:
            text += f"  {femoji or ''} {fname or field_id}: {count} ta\n"
    if busiest:
        text += f"\nEng band vaqt: {busiest[0]} ({busiest[1]} marta)"
    await message.answer(text)

@dp.message(Command("admin"))
async def admin_panel(message: Message):
    if message.from_user.id != OWNER_ID:
        return
    rows = get_upcoming_bookings()
    if not rows:
        await message.answer("📋 Hozircha aktiv bronlar yo'q.")
        return
    await message.answer(f"📋 Jami {len(rows)} ta aktiv bron:")
    for r in rows:
        booking_id, field_id, date, time, user_name, user_id, phone, fname, femoji = r
        phone_line = f"\n📞 {phone}" if phone else "\n📞 raqam yo'q"
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"cancel|{booking_id}")]
        ])
        await message.answer(
            f"{femoji} {fname}\n📅 {date}  🕐 {time}\n👤 {user_name}{phone_line}",
            reply_markup=keyboard
        )

@dp.message(F.text == "📋 Bronlar")
async def btn_admin_panel(message: Message):
    if message.from_user.id != OWNER_ID:
        return
    ADMIN_STATE.pop(message.from_user.id, None)
    await admin_panel(message)

@dp.message(F.text == "➕ Bron qo'shish")
async def btn_admin_add(message: Message):
    user_id = message.from_user.id
    if user_id == OWNER_ID:
        fields = get_approved_fields()
    else:
        fields = get_owned_fields(user_id)
        if not fields:
            return
    ADMIN_STATE[user_id] = {"step": "field"}
    buttons = [[InlineKeyboardButton(text=f"{f[4]} {f[2]}", callback_data=f"aset|{f[0]}")] for f in fields]
    await message.answer("📞 Telefon orqali kelgan mijoz uchun bron qo'shish\n\nQaysi maydon?", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

@dp.message(Command("add"))
async def admin_add_command(message: Message):
    await btn_admin_add(message)

@dp.message(F.text == "📊 Statistika")
async def btn_stats(message: Message):
    if message.from_user.id != OWNER_ID:
        return
    ADMIN_STATE.pop(message.from_user.id, None)
    await stats_command(message)

@dp.message(F.text == "🗑 Maydonlarni boshqarish")
async def btn_manage_fields(message: Message):
    if message.from_user.id != OWNER_ID:
        return
    rows = get_all_fields()
    if not rows:
        await message.answer("Hozircha maydon yo'q.")
        return
    await message.answer(f"🗂 Jami {len(rows)} ta maydon (faol va kutilayotgan):")
    for f in rows:
        field_id, region, name, price, emoji, location, owner_id, status = f
        status_label = "✅ faol" if status == "approved" else "⏳ kutilmoqda"
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🗑 O'chirish", callback_data=f"fdel|{field_id}")]
        ])
        await message.answer(
            f"{emoji} {name} ({status_label})\n📍 {region}\n📌 {location}\n💰 {price} so'm",
            reply_markup=kb
        )

@dp.callback_query(F.data.startswith("fdel|"))
async def field_delete_cb(callback: CallbackQuery):
    if callback.from_user.id != OWNER_ID:
        await callback.answer("Ruxsat yo'q", show_alert=True)
        return
    field_id = callback.data.split("|")[1]
    delete_field(field_id)
    await callback.message.edit_text("🗑 Maydon o'chirildi.")
    await callback.answer()

@dp.message(F.text == "🧑‍💼 Admin tayinlash")
async def btn_assign_admin(message: Message):
    if message.from_user.id != OWNER_ID:
        return
    fields = get_approved_fields()
    if not fields:
        await message.answer("Hozircha tasdiqlangan maydon yo'q.")
        return
    buttons = [[InlineKeyboardButton(text=f"{f[4]} {f[2]} ({f[1]})", callback_data=f"assignf|{f[0]}")] for f in fields]
    await message.answer("Qaysi maydonga admin tayinlaysiz?", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

@dp.callback_query(F.data.startswith("assignf|"))
async def assign_pick_field(callback: CallbackQuery):
    if callback.from_user.id != OWNER_ID:
        await callback.answer("Ruxsat yo'q", show_alert=True)
        return
    field_id = callback.data.split("|")[1]
    ASSIGN_STATE[callback.from_user.id] = {"field": field_id}
    await safe_edit(callback, "Endi shu odamning istalgan xabarini menga FORWARD qiling.\n\n(U avval botga /start yozgan bo'lishi shart)")

@dp.message(F.func(lambda m: m.from_user.id == OWNER_ID and m.from_user.id in ASSIGN_STATE and is_forwarded(m)))
async def assign_receive_forward(message: Message):
    st = ASSIGN_STATE.pop(message.from_user.id)
    field_id = st["field"]
    new_admin_id = get_forward_user_id(message)
    if not new_admin_id:
        await message.answer("Kechirasiz, bu odamning maxfiylik sozlamalari ID'ni yashiryapti.\n\n@userinfobot orqali uning ID raqamini oling va menga oddiy matn qilib yuboring.")
        ASSIGN_STATE[message.from_user.id] = {"field": field_id, "manual": True}
        return
    conn = db()
    conn.execute("UPDATE fields SET owner_id=? WHERE id=?", (new_admin_id, field_id))
    conn.commit()
    conn.close()
    f = get_field(field_id)
    await message.answer(f"✅ \"{f[2]}\" maydoniga yangi admin tayinlandi.", reply_markup=admin_menu_keyboard())
    try:
        await bot.send_message(new_admin_id, f"👨‍💼 Sizga \"{f[2]}\" maydoni bo'yicha admin huquqi berildi.\n\nBotga /start yozing — sizga maxsus panel ochiladi.")
    except Exception:
        pass

@dp.message(F.text, F.func(lambda m: m.from_user.id == OWNER_ID and m.from_user.id in ASSIGN_STATE and ASSIGN_STATE.get(m.from_user.id, {}).get("manual") and not m.text.startswith("/")))
async def assign_manual_id(message: Message):
    st = ASSIGN_STATE.pop(message.from_user.id)
    field_id = st["field"]
    digits = "".join(c for c in message.text if c.isdigit())
    if not digits:
        await message.answer("Iltimos, faqat raqam yuboring.")
        ASSIGN_STATE[message.from_user.id] = st
        return
    new_admin_id = int(digits)
    conn = db()
    conn.execute("UPDATE fields SET owner_id=? WHERE id=?", (new_admin_id, field_id))
    conn.commit()
    conn.close()
    f = get_field(field_id)
    await message.answer(f"✅ \"{f[2]}\" maydoniga yangi admin tayinlandi.", reply_markup=admin_menu_keyboard())
    try:
        await bot.send_message(new_admin_id, f"👨‍💼 Sizga \"{f[2]}\" maydoni bo'yicha admin huquqi berildi.")
    except Exception:
        pass

@dp.callback_query(F.data.startswith("cancel|"))
async def cancel_booking(callback: CallbackQuery):
    booking_id = int(callback.data.split("|")[1])
    booking = get_booking(booking_id)
    if not booking:
        await callback.answer("Bu bron allaqachon bekor qilingan", show_alert=True)
        return
    field_id, date, time, user_id, user_name = booking
    if not can_manage(callback.from_user.id, field_id):
        await callback.answer("Sizda ruxsat yo'q", show_alert=True)
        return
    f = get_field(field_id)
    delete_booking(booking_id)
    await callback.message.edit_text(f"❌ Bekor qilindi:\n{f[4]} {f[2]}\n📅 {date} 🕐 {time}\n👤 {user_name}")
    await callback.answer()
    if user_id:
        try:
            await bot.send_message(
                user_id,
                f"⚠️ Kechirasiz, quyidagi broningiz bekor qilindi:\n\n{f[4]} {f[2]}\n📅 {date}\n🕐 {time}\n\nBoshqa vaqtni tanlash uchun \"⚽ Bron qilish\" tugmasini bosing."
            )
        except Exception:
            pass

@dp.callback_query(F.data.startswith("aset|"))
async def admin_add_field(callback: CallbackQuery):
    field_id = callback.data.split("|")[1]
    if not can_manage(callback.from_user.id, field_id):
        await callback.answer("Ruxsat yo'q", show_alert=True)
        return
    ADMIN_STATE[callback.from_user.id] = {"step": "day", "field": field_id}
    buttons = []
    for i in range(7):
        d = now_tj() + timedelta(days=i)
        buttons.append([InlineKeyboardButton(text=d.strftime("%d-%m-%Y") + (" (bugun)" if i == 0 else ""), callback_data=f"aday|{field_id}|{i}")])
    await safe_edit(callback, "Qaysi kunga?", InlineKeyboardMarkup(inline_keyboard=buttons))

@dp.callback_query(F.data.startswith("aday|"))
async def admin_add_day(callback: CallbackQuery):
    parts = callback.data.split("|")
    field_id = parts[1]
    if not can_manage(callback.from_user.id, field_id):
        await callback.answer("Ruxsat yo'q", show_alert=True)
        return
    if len(parts) == 3:
        offset = parts[2]
        date_str = (now_tj() + timedelta(days=int(offset))).strftime("%Y-%m-%d")
    else:
        st = ADMIN_STATE.get(callback.from_user.id, {})
        date_str = st.get("date")
    ADMIN_STATE[callback.from_user.id] = {"step": "time", "field": field_id, "date": date_str}
    await safe_edit(callback, f"🕐 {date_str}\nQaysi vaqt?", slots_menu(field_id, date_str, prefix="apick"))

@dp.callback_query(F.data.startswith("apick|"))
async def admin_add_time(callback: CallbackQuery):
    _, field_id, date_str, time_str = callback.data.split("|")
    if not can_manage(callback.from_user.id, field_id):
        await callback.answer("Ruxsat yo'q", show_alert=True)
        return
    if time_str in get_booked_times(field_id, date_str):
        await callback.answer("Bu vaqt band", show_alert=True)
        return
    ADMIN_STATE[callback.from_user.id] = {"step": "name", "field": field_id, "date": date_str, "time": time_str}
    await callback.answer()
    await callback.message.answer("✍️ Mijozning ism-familiyasini yozing:")

@dp.message(F.text, F.func(lambda m: m.from_user.id in ADMIN_STATE and not m.text.startswith("/")))
async def admin_add_text(message: Message):
    st = ADMIN_STATE[message.from_user.id]
    if st["step"] == "name":
        st["name"] = message.text.strip()
        st["step"] = "phone"
        await message.answer("📞 Mijozning telefon raqamini yozing:")
    elif st["step"] == "phone":
        phone = message.text.strip()
        field_id, date_str, time_str = st["field"], st["date"], st["time"]
        if time_str in get_booked_times(field_id, date_str):
            await message.answer("Kechirasiz, bu vaqt band bo'lib qoldi.")
            ADMIN_STATE.pop(message.from_user.id, None)
            return
        add_booking(field_id, date_str, time_str, 0, st["name"], phone)
        f = get_field(field_id)
        ADMIN_STATE.pop(message.from_user.id, None)
        kb = admin_menu_keyboard() if message.from_user.id == OWNER_ID else owner_menu_keyboard()
        await message.answer(f"✅ Qo'lda bron qo'shildi!\n\n{f[4]} {f[2]}\n📅 {date_str}  🕐 {time_str}\n👤 {st['name']}\n📞 {phone}", reply_markup=kb)

@dp.message(F.text, F.func(lambda m: m.from_user.id in STATE and not m.text.startswith("/")))
async def info_flow_text(message: Message):
    user_id = message.from_user.id
    st = STATE[user_id]

    if st["step"] == "name":
        full_name = message.text.strip()
        if len(full_name) < 3:
            await message.answer("Iltimos, to'liq ism familiyangizni yozing.")
            return
        st["name"] = full_name
        existing_phone, _ = get_user_info(user_id)
        field_id, date_str, time_str = st["pending"]
        if existing_phone:
            STATE.pop(user_id, None)
            save_user_info(user_id, existing_phone, full_name)
            if time_str in get_booked_times(field_id, date_str):
                await message.answer("Kechirasiz, bu vaqt band bo'lib qoldi. Qaytadan urinib ko'ring.")
                return
            await finalize_booking(field_id, date_str, time_str, user_id, full_name, message.from_user.username, existing_phone)
        else:
            st["step"] = "phone"
            await message.answer(
                "📱 Endi ishlaydigan telefon raqamingizni yozing\n(masalan: +998901234567)\n\nyoki pastdagi tugma orqali ulashing:",
                reply_markup=phone_request_keyboard()
            )

    elif st["step"] == "phone":
        phone = message.text.strip()
        digits = "".join(c for c in phone if c.isdigit())
        if len(digits) < 7:
            await message.answer("Iltimos, to'g'ri telefon raqam kiriting (masalan: +998901234567).")
            return
        full_name = st["name"]
        field_id, date_str, time_str = st["pending"]
        STATE.pop(user_id, None)
        save_user_info(user_id, phone, full_name)
        await message.answer("Rahmat!", reply_markup=customer_menu_keyboard())
        if time_str in get_booked_times(field_id, date_str):
            await message.answer("Kechirasiz, bu vaqt band bo'lib qoldi. Qaytadan urinib ko'ring.")
            return
        await finalize_booking(field_id, date_str, time_str, user_id, full_name, message.from_user.username, phone)

@dp.callback_query(F.data == "back_regions")
async def back_regions(callback: CallbackQuery):
    regions = get_regions()
    if not regions:
        await safe_edit(callback, "Hozircha faol maydon yo'q.")
        return
    await safe_edit(callback, "Hududni tanlang:", region_menu())

@dp.callback_query(F.data.startswith("region|"))
async def region_selected(callback: CallbackQuery):
    region_name = callback.data.split("|", 1)[1]
    await safe_edit(callback, f"📍 {region_name}\n\nQaysi maydonni tanlaysiz?", field_menu(region_name))

@dp.callback_query(F.data.startswith("compare|"))
async def compare_fields(callback: CallbackQuery):
    region_name = callback.data.split("|", 1)[1]
    fields = [f for f in get_approved_fields() if f[1] == region_name]
    if len(fields) < 2:
        await callback.answer("Solishtirish uchun kamida 2 ta maydon kerak", show_alert=True)
        return
    text = f"🆚 {region_name}\n\n"
    for f in fields:
        text += f"{f[4]} {f[2]}\n💰 {f[3]} so'm/soat\n📌 {f[5]}\n\n"
    await callback.message.answer(text)
    await callback.answer()

@dp.callback_query(F.data.startswith("field|"))
async def field_selected(callback: CallbackQuery):
    field_id = callback.data.split("|")[1]
    f = get_field(field_id)
    if not f or f[7] != "approved":
        await callback.answer("Bu maydon topilmadi", show_alert=True)
        return
    text = f"{f[4]} {f[2]}\n📍 {f[5]}\n💰 {f[3]} so'm/soat\n\nQachonga bron qilmoqchisiz?"
    photos = get_photos(f[9])
    if photos:
        try:
            await callback.message.delete()
        except TelegramBadRequest:
            pass
        try:
            if len(photos) == 1:
                await bot.send_photo(callback.from_user.id, photo=photos[0], caption=text, reply_markup=day_menu(field_id))
            else:
                media = [InputMediaPhoto(media=photos[0], caption=text)] + [InputMediaPhoto(media=p) for p in photos[1:4]]
                await bot.send_media_group(callback.from_user.id, media=media)
                await bot.send_message(callback.from_user.id, "Qachonga bron qilmoqchisiz?", reply_markup=day_menu(field_id))
        except Exception:
            await bot.send_message(callback.from_user.id, text, reply_markup=day_menu(field_id))
        await callback.answer()
    else:
        await safe_edit(callback, text, day_menu(field_id))

@dp.callback_query(F.data.startswith("days|"))
async def show_days(callback: CallbackQuery):
    field_id = callback.data.split("|")[1]
    await safe_edit(callback, "Kunni tanlang:", days_list(field_id))

@dp.callback_query(F.data.startswith("day|"))
async def show_slots(callback: CallbackQuery):
    _, field_id, offset = callback.data.split("|")
    date_obj = now_tj() + timedelta(days=int(offset))
    date_str = date_obj.strftime("%Y-%m-%d")
    label = date_obj.strftime("%d-%m-%Y")
    await safe_edit(
        callback,
        f"🕐 {label}\n\n🟢 bo'sh  🔴 band  🟡 o'tgan\nVaqtni tanlang:",
        slots_menu(field_id, date_str)
    )

@dp.callback_query(F.data == "taken")
async def taken(callback: CallbackQuery):
    await callback.answer("Bu vaqt band yoki o'tib ketgan", show_alert=True)

@dp.callback_query(F.data.startswith("book|"))
async def book_slot(callback: CallbackQuery):
    _, field_id, date_str, time_str = callback.data.split("|")
    if time_str in get_booked_times(field_id, date_str):
        await callback.answer("Kechirasiz, bu vaqt band bo'ldi", show_alert=True)
        return
    await callback.answer()
    phone, full_name = get_user_info(callback.from_user.id)
    if phone and full_name:
        await finalize_booking(field_id, date_str, time_str, callback.from_user.id, full_name, callback.from_user.username, phone)
        f = get_field(field_id)
        try:
            await callback.message.edit_text(f"✅ Bron qilindi!\n\n{f[4]} {f[2]}\n📅 {date_str}\n🕐 {time_str}")
        except TelegramBadRequest:
            try:
                await callback.message.edit_caption(caption=f"✅ Bron qilindi!\n\n{f[4]} {f[2]}\n📅 {date_str}\n🕐 {time_str}")
            except (TelegramBadRequest, TypeError):
                pass
    else:
        await start_info_flow(callback.from_user.id, (field_id, date_str, time_str))

async def reminder_loop():
    while True:
        try:
            now = now_tj()
            target = now + timedelta(hours=1)
            target_date = target.strftime("%Y-%m-%d")
            target_hour_str = f"{target.hour:02d}:00"
            conn = db()
            rows = conn.execute(
                "SELECT id, field, date, time, user_id FROM bookings WHERE date=? AND time=? AND (reminded IS NULL OR reminded=0) AND user_id>0",
                (target_date, target_hour_str)
            ).fetchall()
            for r in rows:
                booking_id, field_id, date, time, user_id = r
                f = get_field(field_id)
                if f:
                    try:
                        await bot.send_message(
                            user_id,
                            f"⏰ Eslatma!\n\nBugun soat {time} da {f[4]} {f[2]} da o'yiningiz bor!\n📍 {f[5]}\n\nO'z vaqtida yetib boring!"
                        )
                    except Exception:
                        pass
                conn.execute("UPDATE bookings SET reminded=1 WHERE id=?", (booking_id,))
            conn.commit()
            conn.close()
        except Exception:
            pass
        await asyncio.sleep(60)

async def handle_health(request):
    return web.Response(text="O'yingoh bot ishlayapti")

async def handle_slots(request):
    field_id = request.query.get("field")
    date_str = request.query.get("date")
    if not (field_id and date_str):
        return web.json_response({"error": "missing params"}, status=400)
    booked = set(get_booked_times(field_id, date_str))
    now = now_tj()
    is_today = date_str == now.strftime("%Y-%m-%d")
    result = []
    for h in HOURS:
        status = "free"
        if h in booked:
            status = "booked"
        elif is_today and int(h.split(":")[0]) <= now.hour:
            status = "past"
        result.append({"time": h, "status": status})
    return web.json_response({"slots": result})

@web.middleware
async def cors_middleware(request, handler):
    if request.method == "OPTIONS":
        resp = web.Response()
    else:
        resp = await handler(request)
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return resp

async def start_web_app():
    app = web.Application(middlewares=[cors_middleware])
    app.router.add_get("/", handle_health)
    app.router.add_get("/api/slots", handle_slots)
    app.router.add_route("OPTIONS", "/api/slots", handle_health)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

async def main():
    init_db()
    await start_web_app()
    asyncio.create_task(reminder_loop())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

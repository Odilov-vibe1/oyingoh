import asyncio
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
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
        [KeyboardButton(text="📊 Statistika")]
    ], resize_keyboard=True)

def customer_menu_keyboard():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="⚽ Bron qilish")],
        [KeyboardButton(text="📋 Mening bronlarim")],
        [KeyboardButton(text="🏟 Gazon egasiman")]
    ], resize_keyboard=True)

def init_db():
    conn = db()
    conn.execute("CREATE TABLE IF NOT EXISTS bookings (id INTEGER PRIMARY KEY AUTOINCREMENT, region TEXT, field TEXT, date TEXT, time TEXT, user_id INTEGER, user_name TEXT, phone TEXT)")
    conn.execute("CREATE TABLE IF NOT EXISTS users (telegram_id INTEGER PRIMARY KEY, phone TEXT, full_name TEXT)")
    conn.execute("CREATE TABLE IF NOT EXISTS fields (id TEXT PRIMARY KEY, region TEXT, name TEXT, price TEXT, emoji TEXT, location TEXT, owner_id INTEGER, status TEXT DEFAULT 'pending')")
    for stmt in [
        "ALTER TABLE bookings ADD COLUMN phone TEXT",
        "ALTER TABLE users ADD COLUMN full_name TEXT",
        "ALTER TABLE fields ADD COLUMN owner_phone TEXT",
        "ALTER TABLE fields ADD COLUMN offer_accepted TEXT",
    ]:
        try:
            conn.execute(stmt)
        except sqlite3.OperationalError:
            pass
    existing = conn.execute("SELECT COUNT(*) FROM fields").fetchone()[0]
    if existing == 0:
        conn.execute("INSERT INTO fields (id,region,name,price,emoji,location,owner_id,status,offer_accepted) VALUES (?,?,?,?,?,?,?,?,?)",
                     ("futbol", "QISHLOQ_NOMI", "Mini Futbol", "140,000", "⚽", "19-maktab yonida", OWNER_ID, "approved", "asoschi"))
        conn.execute("INSERT INTO fields (id,region,name,price,emoji,location,owner_id,status,offer_accepted) VALUES (?,?,?,?,?,?,?,?,?)",
                     ("voleybol", "QISHLOQ_NOMI", "Voleybol", "60,000", "🏐", "19-maktab yonida", OWNER_ID, "approved", "asoschi"))
    conn.commit()
    conn.close()

def get_field(field_id):
    conn = db()
    row = conn.execute("SELECT id,region,name,price,emoji,location,owner_id,status,owner_phone FROM fields WHERE id=?", (field_id,)).fetchone()
    conn.close()
    return row

def get_approved_fields():
    conn = db()
    rows = conn.execute("SELECT id,region,name,price,emoji,location,owner_id FROM fields WHERE status='approved' ORDER BY region, name").fetchall()
    conn.close()
    return rows

def get_regions():
    regions = {}
    for f in get_approved_fields():
        regions.setdefault(f[1], []).append(f)
    return regions

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
    STATE.pop(message.from_user.id, None)
    ADMIN_STATE.pop(message.from_user.id, None)
    NEWFIELD_STATE.pop(message.from_user.id, None)
    if message.from_user.id == OWNER_ID:
        await message.answer("👨‍💼 Admin panelga xush kelibsiz!\n\nQuyidagi tugmalardan foydalaning:", reply_markup=admin_menu_keyboard())
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
    if len(regions) == 1:
        region_name = list(regions.keys())[0]
        await message.answer(f"📍 {region_name}\n\nQaysi maydonni tanlaysiz?", reply_markup=field_menu(region_name))
    else:
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

@dp.message(F.text == "🏟 Gazon egasiman")
async def btn_add_field(message: Message):
    NEWFIELD_STATE[message.from_user.id] = {"step": "region"}
    await message.answer("🏟 Yangi maydon qo'shish\n\nHududingiz nomini yozing (masalan: Yakkabog'):")

@dp.message(F.text, F.func(lambda m: m.from_user.id in NEWFIELD_STATE and not m.text.startswith("/")))
async def newfield_flow(message: Message):
    st = NEWFIELD_STATE[message.from_user.id]
    if st["step"] == "region":
        st["region"] = message.text.strip()
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
        st["step"] = "location"
        await message.answer("Maydon manzilini yozing (masalan: Markaziy maydon yonida):")
    elif st["step"] == "location":
        st["location"] = message.text.strip()
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
        st["step"] = "offer"
        await message.answer(OFFER_TEXT, reply_markup=ReplyKeyboardRemove())
    elif st["step"] == "offer":
        if message.text.strip().lower() != "roziman":
            await message.answer("Davom etish uchun aniq \"Roziman\" deb yozing.")
            return
        field_id = f"f{int(datetime.now().timestamp())}"
        conn = db()
        conn.execute(
            "INSERT INTO fields (id,region,name,price,emoji,location,owner_id,status,owner_phone,offer_accepted) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (field_id, st["region"], st["name"], st["price"], "🏟", st["location"], message.from_user.id, "pending", st["phone"], now_tj().strftime("%Y-%m-%d %H:%M"))
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
            try:
                await bot.send_message(
                    OWNER_ID,
                    f"🆕 Yangi maydon so'rovi:\n\n📍 {st['region']}\n🏟 {st['name']}\n💰 {st['price']} so'm/soat\n📌 {st['location']}\n📞 Egasi raqami: {st['phone']}\n👤 @{message.from_user.username or message.from_user.first_name}\n\n⚠️ Tasdiqlashdan oldin raqamiga qo'ng'iroq qilib tekshiring!",
                    reply_markup=kb
                )
            except Exception:
                pass

@dp.message(F.contact)
async def contact_received(message: Message):
    user_id = message.from_user.id

    nf = NEWFIELD_STATE.get(user_id)
    if nf and nf.get("step") == "phone":
        nf["phone"] = message.contact.phone_number
        nf["step"] = "offer"
        await message.answer(OFFER_TEXT, reply_markup=ReplyKeyboardRemove())
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
    await callback.message.edit_text(f"✅ Tasdiqlandi: {f[2] if f else field_id}")
    await callback.answer()
    if f and f[6]:
        try:
            await bot.send_message(f[6], f"🎉 Tabriklaymiz! \"{f[2]}\" maydoningiz tasdiqlandi va botda faol bo'ldi.")
        except Exception:
            pass

@dp.callback_query(F.data.startswith("freject|"))
async def field_reject(callback: CallbackQuery):
    if callback.from_user.id != OWNER_ID:
        await callback.answer("Ruxsat yo'q", show_alert=True)
        return
    field_id = callback.data.split("|")[1]
    f = get_field(field_id)
    conn = db()
    conn.execute("DELETE FROM fields WHERE id=?", (field_id,))
    conn.commit()
    conn.close()
    await callback.message.edit_text("❌ Rad etildi.")
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

@dp.message(Command("add"))
async def admin_add_start(message: Message):
    if message.from_user.id != OWNER_ID:
        return
    ADMIN_STATE[message.from_user.id] = {"step": "field"}
    fields = get_approved_fields()
    buttons = [[InlineKeyboardButton(text=f"{f[4]} {f[2]}", callback_data=f"aset|{f[0]}")] for f in fields]
    await message.answer("📞 Telefon orqali kelgan mijoz uchun bron qo'shish\n\nQaysi maydon?", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

@dp.message(F.text == "📋 Bronlar")
async def btn_admin_panel(message: Message):
    if message.from_user.id != OWNER_ID:
        return
    ADMIN_STATE.pop(message.from_user.id, None)
    await admin_panel(message)

@dp.message(F.text == "➕ Bron qo'shish")
async def btn_admin_add(message: Message):
    if message.from_user.id != OWNER_ID:
        return
    await admin_add_start(message)

@dp.message(F.text == "📊 Statistika")
async def btn_stats(message: Message):
    if message.from_user.id != OWNER_ID:
        return
    ADMIN_STATE.pop(message.from_user.id, None)
    await stats_command(message)

@dp.callback_query(F.data.startswith("cancel|"))
async def cancel_booking(callback: CallbackQuery):
    if callback.from_user.id != OWNER_ID:
        await callback.answer("Sizda ruxsat yo'q", show_alert=True)
        return
    booking_id = int(callback.data.split("|")[1])
    booking = get_booking(booking_id)
    if not booking:
        await callback.answer("Bu bron allaqachon bekor qilingan", show_alert=True)
        return
    field_id, date, time, user_id, user_name = booking
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
    if callback.from_user.id != OWNER_ID:
        await callback.answer("Ruxsat yo'q", show_alert=True)
        return
    field_id = callback.data.split("|")[1]
    ADMIN_STATE[callback.from_user.id] = {"step": "day", "field": field_id}
    buttons = []
    for i in range(7):
        d = now_tj() + timedelta(days=i)
        buttons.append([InlineKeyboardButton(text=d.strftime("%d-%m-%Y") + (" (bugun)" if i == 0 else ""), callback_data=f"aday|{field_id}|{i}")])
    await safe_edit(callback, "Qaysi kunga?", InlineKeyboardMarkup(inline_keyboard=buttons))

@dp.callback_query(F.data.startswith("aday|"))
async def admin_add_day(callback: CallbackQuery):
    if callback.from_user.id != OWNER_ID:
        await callback.answer("Ruxsat yo'q", show_alert=True)
        return
    parts = callback.data.split("|")
    if len(parts) == 3:
        _, field_id, offset = parts
        date_str = (now_tj() + timedelta(days=int(offset))).strftime("%Y-%m-%d")
    else:
        _, field_id = parts
        st = ADMIN_STATE.get(callback.from_user.id, {})
        date_str = st.get("date")
    ADMIN_STATE[callback.from_user.id] = {"step": "time", "field": field_id, "date": date_str}
    await safe_edit(callback, f"🕐 {date_str}\nQaysi vaqt?", slots_menu(field_id, date_str, prefix="apick"))

@dp.callback_query(F.data.startswith("apick|"))
async def admin_add_time(callback: CallbackQuery):
    if callback.from_user.id != OWNER_ID:
        await callback.answer("Ruxsat yo'q", show_alert=True)
        return
    _, field_id, date_str, time_str = callback.data.split("|")
    if time_str in get_booked_times(field_id, date_str):
        await callback.answer("Bu vaqt band", show_alert=True)
        return
    ADMIN_STATE[callback.from_user.id] = {"step": "name", "field": field_id, "date": date_str, "time": time_str}
    await callback.answer()
    await callback.message.answer("✍️ Mijozning ism-familiyasini yozing:")

@dp.message(F.text, F.func(lambda m: m.from_user.id == OWNER_ID and m.from_user.id in ADMIN_STATE and not m.text.startswith("/")))
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
        await message.answer(f"✅ Qo'lda bron qo'shildi!\n\n{f[4]} {f[2]}\n📅 {date_str}  🕐 {time_str}\n👤 {st['name']}\n📞 {phone}", reply_markup=admin_menu_keyboard())

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
    if len(regions) == 1:
        region_name = list(regions.keys())[0]
        await safe_edit(callback, f"📍 {region_name}\n\nQaysi maydonni tanlaysiz?", field_menu(region_name))
    else:
        await safe_edit(callback, "Hududni tanlang:", region_menu())

@dp.callback_query(F.data.startswith("region|"))
async def region_selected(callback: CallbackQuery):
    region_name = callback.data.split("|", 1)[1]
    await safe_edit(callback, f"📍 {region_name}\n\nQaysi maydonni tanlaysiz?", field_menu(region_name))

@dp.callback_query(F.data.startswith("field|"))
async def field_selected(callback: CallbackQuery):
    field_id = callback.data.split("|")[1]
    f = get_field(field_id)
    if not f or f[7] != "approved":
        await callback.answer("Bu maydon topilmadi", show_alert=True)
        return
    await safe_edit(
        callback,
        f"{f[4]} {f[2]}\n📍 {f[5]}\n💰 {f[3]} so'm/soat\n\nQachonga bron qilmoqchisiz?",
        day_menu(field_id)
    )

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
            pass
    else:
        await start_info_flow(callback.from_user.id, (field_id, date_str, time_str))

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
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

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

TASHKENT = timezone(timedelta(hours=5))

def now_tj():
    return datetime.now(TASHKENT)

REGIONS = {
    "qishloq1": {
        "name": "QISHLOQ_NOMI",
        "fields": {
            "futbol": {"name": "Mini Futbol", "price": "140,000", "emoji": "⚽", "location": "19-maktab yonida"},
            "voleybol": {"name": "Voleybol", "price": "60,000", "emoji": "🏐", "location": "19-maktab yonida"},
        }
    }
}
HOURS = [f"{h:02d}:00" for h in range(5, 23)]
STATE = {}
ADMIN_STATE = {}

def get_field_info(region_id, field_id):
    return REGIONS[region_id]["fields"][field_id]

async def safe_edit(callback: CallbackQuery, text: str, keyboard=None):
    try:
        await callback.message.edit_text(text, reply_markup=keyboard)
    except TelegramBadRequest:
        pass
    await callback.answer()

def init_db():
    conn = sqlite3.connect("bookings.db")
    conn.execute("CREATE TABLE IF NOT EXISTS bookings (id INTEGER PRIMARY KEY AUTOINCREMENT, region TEXT, field TEXT, date TEXT, time TEXT, user_id INTEGER, user_name TEXT, phone TEXT)")
    conn.execute("CREATE TABLE IF NOT EXISTS users (telegram_id INTEGER PRIMARY KEY, phone TEXT, full_name TEXT)")
    for stmt in ["ALTER TABLE bookings ADD COLUMN phone TEXT", "ALTER TABLE users ADD COLUMN full_name TEXT"]:
        try:
            conn.execute(stmt)
        except sqlite3.OperationalError:
            pass
    conn.commit()
    conn.close()

def get_user_info(user_id):
    conn = sqlite3.connect("bookings.db")
    row = conn.execute("SELECT phone, full_name FROM users WHERE telegram_id=?", (user_id,)).fetchone()
    conn.close()
    return (row[0], row[1]) if row else (None, None)

def save_user_info(user_id, phone, full_name):
    conn = sqlite3.connect("bookings.db")
    conn.execute("INSERT OR REPLACE INTO users (telegram_id, phone, full_name) VALUES (?,?,?)", (user_id, phone, full_name))
    conn.commit()
    conn.close()

def get_booked_times(region, field, date):
    conn = sqlite3.connect("bookings.db")
    rows = [r[0] for r in conn.execute("SELECT time FROM bookings WHERE region=? AND field=? AND date=?", (region, field, date)).fetchall()]
    conn.close()
    return rows

def add_booking(region, field, date, time, user_id, user_name, phone):
    conn = sqlite3.connect("bookings.db")
    conn.execute("INSERT INTO bookings (region, field, date, time, user_id, user_name, phone) VALUES (?,?,?,?,?,?,?)", (region, field, date, time, user_id, user_name, phone))
    conn.commit()
    conn.close()

def get_upcoming_bookings():
    today = now_tj().strftime("%Y-%m-%d")
    conn = sqlite3.connect("bookings.db")
    rows = conn.execute(
        "SELECT id, region, field, date, time, user_name, user_id, phone FROM bookings WHERE date>=? ORDER BY date, time", (today,)
    ).fetchall()
    conn.close()
    return rows

def get_booking(booking_id):
    conn = sqlite3.connect("bookings.db")
    row = conn.execute("SELECT region, field, date, time, user_id, user_name FROM bookings WHERE id=?", (booking_id,)).fetchone()
    conn.close()
    return row

def delete_booking(booking_id):
    conn = sqlite3.connect("bookings.db")
    conn.execute("DELETE FROM bookings WHERE id=?", (booking_id,))
    conn.commit()
    conn.close()

def get_stats():
    conn = sqlite3.connect("bookings.db")
    total = conn.execute("SELECT COUNT(*) FROM bookings").fetchone()[0]
    today = now_tj().strftime("%Y-%m-%d")
    week_end = (now_tj() + timedelta(days=7)).strftime("%Y-%m-%d")
    today_count = conn.execute("SELECT COUNT(*) FROM bookings WHERE date=?", (today,)).fetchone()[0]
    week_count = conn.execute("SELECT COUNT(*) FROM bookings WHERE date>=? AND date<=?", (today, week_end)).fetchone()[0]
    per_field = conn.execute("SELECT region, field, COUNT(*) FROM bookings GROUP BY region, field ORDER BY COUNT(*) DESC").fetchall()
    busiest = conn.execute("SELECT time, COUNT(*) c FROM bookings GROUP BY time ORDER BY c DESC LIMIT 1").fetchone()
    conn.close()
    return total, today_count, week_count, per_field, busiest

def region_menu():
    buttons = [[InlineKeyboardButton(text=f"📍 {r['name']}", callback_data=f"region|{rid}")] for rid, r in REGIONS.items()]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def field_menu(region_id):
    fields = REGIONS[region_id]["fields"]
    buttons = [[InlineKeyboardButton(text=f"{f['emoji']} {f['name']} — {f['price']} so'm", callback_data=f"field|{region_id}|{fid}")] for fid, f in fields.items()]
    buttons.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_regions")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def day_menu(region_id, field_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📅 Bugun", callback_data=f"day|{region_id}|{field_id}|0")],
        [InlineKeyboardButton(text="🗓 Boshqa kun", callback_data=f"days|{region_id}|{field_id}")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data=f"region|{region_id}")],
    ])

def days_list(region_id, field_id):
    buttons = []
    for i in range(7):
        d = now_tj() + timedelta(days=i)
        buttons.append([InlineKeyboardButton(text=d.strftime("%d-%m"), callback_data=f"day|{region_id}|{field_id}|{i}")])
    buttons.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data=f"field|{region_id}|{field_id}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def slots_menu(region_id, field_id, date_str, prefix="book"):
    booked = get_booked_times(region_id, field_id, date_str)
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
            row.append(InlineKeyboardButton(text=f"🟢 {h}", callback_data=f"{prefix}|{region_id}|{field_id}|{date_str}|{h}"))
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    back_cb = f"field|{region_id}|{field_id}" if prefix == "book" else f"aday|{region_id}|{field_id}"
    buttons.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data=back_cb)])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def phone_request_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Raqamni ulashish", request_contact=True)]],
        resize_keyboard=True, one_time_keyboard=True
    )

async def finalize_booking(region_id, field_id, date_str, time_str, user_id, full_name, username, phone):
    add_booking(region_id, field_id, date_str, time_str, user_id, full_name, phone)
    info = get_field_info(region_id, field_id)
    await bot.send_message(
        user_id,
        f"✅ Bron qilindi!\n\n{info['emoji']} {info['name']}\n📅 {date_str}\n🕐 {time_str}\n\nTez orada siz bilan bog'lanishadi."
    )
    if OWNER_ID:
        try:
            await bot.send_message(
                OWNER_ID,
                f"🔔 Yangi bron!\n\n{info['emoji']} {info['name']}\n📅 {date_str}  🕐 {time_str}\n👤 {full_name} (@{username or 'yoq'})\n📞 {phone}"
            )
        except Exception:
            pass

async def start_info_flow(user_id, pending):
    STATE[user_id] = {"step": "name", "pending": pending}
    await bot.send_message(user_id, "✍️ Bronni tasdiqlash uchun ism va familiyangizni to'liq yozing\n(masalan: Aliyev Vali):")

@dp.message(CommandStart())
async def start(message: Message):
    STATE.pop(message.from_user.id, None)
    if len(REGIONS) == 1:
        region_id = list(REGIONS.keys())[0]
        await message.answer(
            f"⚽ Xush kelibsiz, {message.from_user.first_name}!\n\n🏟 O'yingoh — maydon bron qilish boti!\n📍 {REGIONS[region_id]['name']}\n\nQaysi maydonni tanlaysiz?",
            reply_markup=field_menu(region_id)
        )
    else:
        await message.answer(
            f"⚽ Xush kelibsiz, {message.from_user.first_name}!\n\n🏟 O'yingoh — maydon bron qilish boti!\n\nHududni tanlang:",
            reply_markup=region_menu()
        )

@dp.message(F.contact)
async def contact_received(message: Message):
    user_id = message.from_user.id
    st = STATE.get(user_id)
    if not st or st["step"] != "phone":
        return
    if not message.contact or message.contact.user_id != user_id:
        await message.answer("⚠️⚠️⚠️Iltimos, faqat o'z raqamingizni yuboring.Adminlar siz bilan bog'lanishlari kerak, aks holda bron bekor qilinadi!")
        return
    phone = message.contact.phone_number
    full_name = st["name"]
    region_id, field_id, date_str, time_str = st["pending"]
    STATE.pop(user_id, None)
    save_user_info(user_id, phone, full_name)
    await message.answer("Rahmat!", reply_markup=ReplyKeyboardRemove())
    if time_str in get_booked_times(region_id, field_id, date_str):
        await message.answer("Kechirasiz, navbatingizda ushbu vaqt band bo'lib qoldi. /start orqali qaytadan urinib ko'ring.")
        return
    await finalize_booking(region_id, field_id, date_str, time_str, user_id, full_name, message.from_user.username, phone)

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
        region_id, field_id, date_str, time_str = st["pending"]
        if existing_phone:
            STATE.pop(user_id, None)
            save_user_info(user_id, existing_phone, full_name)
            if time_str in get_booked_times(region_id, field_id, date_str):
                await message.answer("Kechirasiz, bu vaqt band bo'lib qoldi. /start orqali qaytadan urinib ko'ring.")
                return
            await finalize_booking(region_id, field_id, date_str, time_str, user_id, full_name, message.from_user.username, existing_phone)
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
        region_id, field_id, date_str, time_str = st["pending"]
        STATE.pop(user_id, None)
        save_user_info(user_id, phone, full_name)
        await message.answer("Rahmat!", reply_markup=ReplyKeyboardRemove())
        if time_str in get_booked_times(region_id, field_id, date_str):
            await message.answer("Kechirasiz, bu vaqt band bo'lib qoldi. /start orqali qaytadan urinib ko'ring.")
            return
        await finalize_booking(region_id, field_id, date_str, time_str, user_id, full_name, message.from_user.username, phone)

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
        for region_id, field_id, count in per_field:
            info = get_field_info(region_id, field_id)
            text += f"  {info['emoji']} {info['name']}: {count} ta\n"
    if busiest:
        text += f"\nEng band vaqt: {busiest[0]} ({busiest[1]} marta)"
    await message.answer(text)

@dp.message(Command("admin"))
async def admin_panel(message: Message):
    if message.from_user.id != OWNER_ID:
        return
    rows = get_upcoming_bookings()
    if not rows:
        await message.answer("📋 Hozircha aktiv bronlar yo'q.\n\n➕ Qo'lda bron qo'shish uchun /add yozing.")
        return
    await message.answer(f"📋 Jami {len(rows)} ta aktiv bron:\n\n➕ Qo'lda qo'shish uchun /add")
    for r in rows:
        booking_id, region_id, field_id, date, time, user_name, user_id, phone = r
        info = get_field_info(region_id, field_id)
        phone_line = f"\n📞 {phone}" if phone else "\n📞 raqam yo'q"
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"cancel|{booking_id}")]
        ])
        await message.answer(
            f"{info['emoji']} {info['name']}\n📅 {date}  🕐 {time}\n👤 {user_name}{phone_line}",
            reply_markup=keyboard
        )

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
    region_id, field_id, date, time, user_id, user_name = booking
    info = get_field_info(region_id, field_id)
    delete_booking(booking_id)
    await callback.message.edit_text(f"❌ Bekor qilindi:\n{info['emoji']} {info['name']}\n📅 {date} 🕐 {time}\n👤 {user_name}")
    await callback.answer()
    if user_id:
        try:
            await bot.send_message(
                user_id,
                f"⚠️ Kechirasiz, quyidagi broningiz bekor qilindi:\n\n{info['emoji']} {info['name']}\n📅 {date}\n🕐 {time}\n\nBoshqa vaqtni tanlash uchun /start bosing."
            )
        except Exception:
            pass

@dp.message(Command("add"))
async def admin_add_start(message: Message):
    if message.from_user.id != OWNER_ID:
        return
    ADMIN_STATE[message.from_user.id] = {"step": "field"}
    region_id = list(REGIONS.keys())[0]
    buttons = [[InlineKeyboardButton(text=f"{f['emoji']} {f['name']}", callback_data=f"aset|{region_id}|{fid}")] for fid, f in REGIONS[region_id]["fields"].items()]
    await message.answer("📞 Telefon orqali kelgan mijoz uchun bron qo'shish\n\nQaysi maydon?", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

@dp.callback_query(F.data.startswith("aset|"))
async def admin_add_field(callback: CallbackQuery):
    if callback.from_user.id != OWNER_ID:
        await callback.answer("Ruxsat yo'q", show_alert=True)
        return
    _, region_id, field_id = callback.data.split("|")
    ADMIN_STATE[callback.from_user.id] = {"step": "day", "region": region_id, "field": field_id}
    buttons = []
    for i in range(7):
        d = now_tj() + timedelta(days=i)
        buttons.append([InlineKeyboardButton(text=d.strftime("%d-%m-%Y") + (" (bugun)" if i == 0 else ""), callback_data=f"aday|{region_id}|{field_id}|{i}")])
    await safe_edit(callback, "Qaysi kunga?", InlineKeyboardMarkup(inline_keyboard=buttons))

@dp.callback_query(F.data.startswith("aday|"))
async def admin_add_day(callback: CallbackQuery):
    if callback.from_user.id != OWNER_ID:
        await callback.answer("Ruxsat yo'q", show_alert=True)
        return
    parts = callback.data.split("|")
    if len(parts) == 4:
        _, region_id, field_id, offset = parts
        date_str = (now_tj() + timedelta(days=int(offset))).strftime("%Y-%m-%d")
    else:
        _, region_id, field_id = parts
        st = ADMIN_STATE.get(callback.from_user.id, {})
        date_str = st.get("date")
    ADMIN_STATE[callback.from_user.id] = {"step": "time", "region": region_id, "field": field_id, "date": date_str}
    await safe_edit(callback, f"🕐 {date_str}\nQaysi vaqt?", slots_menu(region_id, field_id, date_str, prefix="apick"))

@dp.callback_query(F.data.startswith("apick|"))
async def admin_add_time(callback: CallbackQuery):
    if callback.from_user.id != OWNER_ID:
        await callback.answer("Ruxsat yo'q", show_alert=True)
        return
    _, region_id, field_id, date_str, time_str = callback.data.split("|")
    if time_str in get_booked_times(region_id, field_id, date_str):
        await callback.answer("Bu vaqt band", show_alert=True)
        return
    ADMIN_STATE[callback.from_user.id] = {"step": "name", "region": region_id, "field": field_id, "date": date_str, "time": time_str}
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
        region_id, field_id, date_str, time_str = st["region"], st["field"], st["date"], st["time"]
        if time_str in get_booked_times(region_id, field_id, date_str):
            await message.answer("Kechirasiz, bu vaqt band bo'lib qoldi.")
            ADMIN_STATE.pop(message.from_user.id, None)
            return
        add_booking(region_id, field_id, date_str, time_str, 0, st["name"], phone)
        info = get_field_info(region_id, field_id)
        ADMIN_STATE.pop(message.from_user.id, None)
        await message.answer(f"✅ Qo'lda bron qo'shildi!\n\n{info['emoji']} {info['name']}\n📅 {date_str}  🕐 {time_str}\n👤 {st['name']}\n📞 {phone}")

@dp.callback_query(F.data == "back_regions")
async def back_regions(callback: CallbackQuery):
    if len(REGIONS) == 1:
        region_id = list(REGIONS.keys())[0]
        await safe_edit(callback, f"📍 {REGIONS[region_id]['name']}\n\nQaysi maydonni tanlaysiz?", field_menu(region_id))
    else:
        await safe_edit(callback, "Hududni tanlang:", region_menu())

@dp.callback_query(F.data.startswith("region|"))
async def region_selected(callback: CallbackQuery):
    region_id = callback.data.split("|")[1]
    await safe_edit(callback, f"📍 {REGIONS[region_id]['name']}\n\nQaysi maydonni tanlaysiz?", field_menu(region_id))

@dp.callback_query(F.data.startswith("field|"))
async def field_selected(callback: CallbackQuery):
    _, region_id, field_id = callback.data.split("|")
    info = get_field_info(region_id, field_id)
    await safe_edit(
        callback,
        f"{info['emoji']} {info['name']}\n📍 {info['location']}\n💰 {info['price']} so'm/soat\n\nQachonga bron qilmoqchisiz?",
        day_menu(region_id, field_id)
    )

@dp.callback_query(F.data.startswith("days|"))
async def show_days(callback: CallbackQuery):
    _, region_id, field_id = callback.data.split("|")
    await safe_edit(callback, "Kunni tanlang:", days_list(region_id, field_id))

@dp.callback_query(F.data.startswith("day|"))
async def show_slots(callback: CallbackQuery):
    _, region_id, field_id, offset = callback.data.split("|")
    date_obj = now_tj() + timedelta(days=int(offset))
    date_str = date_obj.strftime("%Y-%m-%d")
    label = date_obj.strftime("%d-%m-%Y")
    await safe_edit(
        callback,
        f"🕐 {label}\n\n🟢 bo'sh  🔴 band  🟡 o'tgan\nVaqtni tanlang:",
        slots_menu(region_id, field_id, date_str)
    )

@dp.callback_query(F.data == "taken")
async def taken(callback: CallbackQuery):
    await callback.answer("Bu vaqt band yoki o'tib ketgan", show_alert=True)

@dp.callback_query(F.data.startswith("book|"))
async def book_slot(callback: CallbackQuery):
    _, region_id, field_id, date_str, time_str = callback.data.split("|")
    if time_str in get_booked_times(region_id, field_id, date_str):
        await callback.answer("Kechirasiz, bu vaqt band bo'ldi", show_alert=True)
        return
    await callback.answer()
    phone, full_name = get_user_info(callback.from_user.id)
    if phone and full_name:
        await finalize_booking(region_id, field_id, date_str, time_str, callback.from_user.id, full_name, callback.from_user.username, phone)
        info = get_field_info(region_id, field_id)
        try:
            await callback.message.edit_text(f"✅ Bron qilindi!\n\n{info['emoji']} {info['name']}\n📅 {date_str}\n🕐 {time_str}")
        except TelegramBadRequest:
            pass
    else:
        await start_info_flow(callback.from_user.id, (region_id, field_id, date_str, time_str))

async def handle_health(request):
    return web.Response(text="O'yingoh bot ishlayapti")

async def handle_slots(request):
    region = request.query.get("region")
    field = request.query.get("field")
    date_str = request.query.get("date")
    if not (region and field and date_str):
        return web.json_response({"error": "missing params"}, status=400)
    booked = set(get_booked_times(region, field, date_str))
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

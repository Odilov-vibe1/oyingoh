import asyncio
import os
import sqlite3
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart, Command
from aiogram.exceptions import TelegramBadRequest

TOKEN = os.environ.get("BOT_TOKEN")
OWNER_ID = int(os.environ.get("OWNER_ID", "0"))

bot = Bot(token=TOKEN)
dp = Dispatcher()

# ============ HUDUD VA MAYDONLAR ============
# Yangi qishloq/gazon qo'shish uchun shu yerga yangi kalit qo'shing
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
    conn.execute("CREATE TABLE IF NOT EXISTS bookings (id INTEGER PRIMARY KEY AUTOINCREMENT, region TEXT, field TEXT, date TEXT, time TEXT, user_id INTEGER, user_name TEXT)")
    conn.commit()
    conn.close()

def get_booked_times(region, field, date):
    conn = sqlite3.connect("bookings.db")
    rows = [r[0] for r in conn.execute("SELECT time FROM bookings WHERE region=? AND field=? AND date=?", (region, field, date)).fetchall()]
    conn.close()
    return rows

def add_booking(region, field, date, time, user_id, user_name):
    conn = sqlite3.connect("bookings.db")
    conn.execute("INSERT INTO bookings (region, field, date, time, user_id, user_name) VALUES (?,?,?,?,?,?)", (region, field, date, time, user_id, user_name))
    conn.commit()
    conn.close()

def get_upcoming_bookings():
    today = datetime.now().strftime("%Y-%m-%d")
    conn = sqlite3.connect("bookings.db")
    rows = conn.execute("SELECT id, region, field, date, time, user_name, user_id FROM bookings WHERE date>=? ORDER BY date, time", (today,)).fetchall()
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

# ============ MENYULAR ============
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
        d = datetime.now() + timedelta(days=i)
        buttons.append([InlineKeyboardButton(text=d.strftime("%d-%m"), callback_data=f"day|{region_id}|{field_id}|{i}")])
    buttons.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data=f"field|{region_id}|{field_id}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def slots_menu(region_id, field_id, date_str):
    booked = get_booked_times(region_id, field_id, date_str)
    buttons, row = [], []
    for h in HOURS:
        if h in booked:
            row.append(InlineKeyboardButton(text=f"🔴 {h}", callback_data="taken"))
        else:
            row.append(InlineKeyboardButton(text=f"🟢 {h}", callback_data=f"book|{region_id}|{field_id}|{date_str}|{h}"))
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data=f"field|{region_id}|{field_id}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# ============ HANDLERLAR ============
@dp.message(CommandStart())
async def start(message: Message):
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
    date_obj = datetime.now() + timedelta(days=int(offset))
    date_str = date_obj.strftime("%Y-%m-%d")
    label = date_obj.strftime("%d-%m-%Y")
    await safe_edit(
        callback,
        f"🕐 {label}\n\n🟢 bo'sh  🔴 band\nVaqtni tanlang:",
        slots_menu(region_id, field_id, date_str)
    )

@dp.callback_query(F.data == "taken")
async def taken(callback: CallbackQuery):
    await callback.answer("Bu vaqt band, boshqasini tanlang", show_alert=True)

@dp.callback_query(F.data.startswith("book|"))
async def book_slot(callback: CallbackQuery):
    _, region_id, field_id, date_str, time_str = callback.data.split("|")
    if time_str in get_booked_times(region_id, field_id, date_str):
        await callback.answer("Kechirasiz, bu vaqt band bo'ldi", show_alert=True)
        return
    user_name = callback.from_user.first_name
    add_booking(region_id, field_id, date_str, time_str, callback.from_user.id, user_name)
    info = get_field_info(region_id, field_id)
    await safe_edit(
        callback,
        f"✅ Bron qilindi!\n\n{info['emoji']} {info['name']}\n📅 {date_str}\n🕐 {time_str}\n\nTez orada siz bilan bog'lanishadi."
    )
    if OWNER_ID:
        try:
            await bot.send_message(
                OWNER_ID,
                f"🔔 Yangi bron!\n\n{info['emoji']} {info['name']}\n📅 {date_str}  🕐 {time_str}\n👤 {user_name} (@{callback.from_user.username or 'yoq'})"
            )
        except Exception:
            pass

# ============ ADMIN PANEL ============
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
        booking_id, region_id, field_id, date, time, user_name, user_id = r
        info = get_field_info(region_id, field_id)
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"cancel|{booking_id}")]
        ])
        await message.answer(
            f"{info['emoji']} {info['name']}\n📅 {date}  🕐 {time}\n👤 {user_name}",
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
    try:
        await bot.send_message(
            user_id,
            f"⚠️ Kechirasiz, quyidagi broningiz bekor qilindi:\n\n{info['emoji']} {info['name']}\n📅 {date}\n🕐 {time}\n\nBoshqa vaqtni tanlash uchun /start bosing."
        )
    except Exception:
        pass

async def main():
    init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

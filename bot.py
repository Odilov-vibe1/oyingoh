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

FIELDS = {
    "futbol": {"name": "Mini Futbol", "price": "140,000", "emoji": "⚽"},
    "voleybol": {"name": "Voleybol", "price": "60,000", "emoji": "🏐"},
}
HOURS = [f"{h:02d}:00" for h in range(5, 23)]

async def safe_edit(callback: CallbackQuery, text: str, keyboard=None):
    try:
        await callback.message.edit_text(text, reply_markup=keyboard)
    except TelegramBadRequest:
        pass
    await callback.answer()

def init_db():
    conn = sqlite3.connect("bookings.db")
    conn.execute("CREATE TABLE IF NOT EXISTS bookings (id INTEGER PRIMARY KEY AUTOINCREMENT, field TEXT, date TEXT, time TEXT, user_id INTEGER, user_name TEXT)")
    conn.commit()
    conn.close()

def get_booked_times(field, date):
    conn = sqlite3.connect("bookings.db")
    rows = [r[0] for r in conn.execute("SELECT time FROM bookings WHERE field=? AND date=?", (field, date)).fetchall()]
    conn.close()
    return rows

def add_booking(field, date, time, user_id, user_name):
    conn = sqlite3.connect("bookings.db")
    conn.execute("INSERT INTO bookings (field, date, time, user_id, user_name) VALUES (?,?,?,?,?)", (field, date, time, user_id, user_name))
    conn.commit()
    conn.close()

def get_upcoming_bookings():
    today = datetime.now().strftime("%Y-%m-%d")
    conn = sqlite3.connect("bookings.db")
    rows = conn.execute("SELECT id, field, date, time, user_name FROM bookings WHERE date>=? ORDER BY date, time", (today,)).fetchall()
    conn.close()
    return rows

def delete_booking(booking_id):
    conn = sqlite3.connect("bookings.db")
    conn.execute("DELETE FROM bookings WHERE id=?", (booking_id,))
    conn.commit()
    conn.close()

def main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚽ Mini Futbol", callback_data="field|futbol")],
        [InlineKeyboardButton(text="🏐 Voleybol", callback_data="field|voleybol")],
    ])

def day_menu(field):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📅 Bugun", callback_data=f"day|{field}|0")],
        [InlineKeyboardButton(text="🗓 Boshqa kun", callback_data=f"days|{field}")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_main")],
    ])

def days_list(field):
    buttons = []
    for i in range(7):
        d = datetime.now() + timedelta(days=i)
        buttons.append([InlineKeyboardButton(text=d.strftime("%d-%m"), callback_data=f"day|{field}|{i}")])
    buttons.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data=f"field|{field}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def slots_menu(field, date_str):
    booked = get_booked_times(field, date_str)
    buttons, row = [], []
    for h in HOURS:
        if h in booked:
            row.append(InlineKeyboardButton(text=f"🔴 {h}", callback_data="taken"))
        else:
            row.append(InlineKeyboardButton(text=f"🟢 {h}", callback_data=f"book|{field}|{date_str}|{h}"))
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data=f"field|{field}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

@dp.message(CommandStart())
async def start(message: Message):
    await message.answer(
        f"⚽ Xush kelibsiz, {message.from_user.first_name}!\n\n🏟 O'yingoh — maydon bron qilish boti!\n\nQaysi maydonni tanlaysiz?",
        reply_markup=main_menu()
    )

@dp.message(Command("admin"))
async def admin_panel(message: Message):
    if message.from_user.id != OWNER_ID:
        return
    rows = get_upcoming_bookings()
    if not rows:
        await message.answer("📋 Hozircha aktiv bronlar yo'q.")
        return
    for r in rows:
        booking_id, field, date, time, user_name = r
        info = FIELDS.get(field, {"name": field, "emoji": ""})
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
    delete_booking(booking_id)
    await callback.message.edit_text("❌ Bron bekor qilindi.")
    await callback.answer()

@dp.callback_query(F.data == "back_main")
async def back_main(callback: CallbackQuery):
    await safe_edit(callback, "Qaysi maydonni tanlaysiz?", main_menu())

@dp.callback_query(F.data.startswith("field|"))
async def field_selected(callback: CallbackQuery):
    field = callback.data.split("|")[1]
    info = FIELDS[field]
    await safe_edit(
        callback,
        f"{info['emoji']} {info['name']}\n💰 {info['price']} so'm/soat\n\nQachonga bron qilmoqchisiz?",
        day_menu(field)
    )

@dp.callback_query(F.data.startswith("days|"))
async def show_days(callback: CallbackQuery):
    field = callback.data.split("|")[1]
    await safe_edit(callback, "Kunni tanlang:", days_list(field))

@dp.callback_query(F.data.startswith("day|"))
async def show_slots(callback: CallbackQuery):
    _, field, offset = callback.data.split("|")
    date_obj = datetime.now() + timedelta(days=int(offset))
    date_str = date_obj.strftime("%Y-%m-%d")
    label = date_obj.strftime("%d-%m-%Y")
    await safe_edit(
        callback,
        f"🕐 {label}\n\n🟢 bo'sh  🔴 band\nVaqtni tanlang:",
        slots_menu(field, date_str)
    )

@dp.callback_query(F.data == "taken")
async def taken(callback: CallbackQuery):
    await callback.answer("Bu vaqt band, boshqasini tanlang", show_alert=True)

@dp.callback_query(F.data.startswith("book|"))
async def book_slot(callback: CallbackQuery):
    _, field, date_str, time_str = callback.data.split("|")
    if time_str in get_booked_times(field, date_str):
        await callback.answer("Kechirasiz, bu vaqt band bo'ldi", show_alert=True)
        return
    user_name = callback.from_user.first_name
    add_booking(field, date_str, time_str, callback.from_user.id, user_name)
    info = FIELDS[field]
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

async def main():
    init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

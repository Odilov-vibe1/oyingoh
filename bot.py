import asyncio
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart
import os

TOKEN = os.environ.get("BOT_TOKEN")

bot = Bot(token=TOKEN)
dp = Dispatcher()

def main_menu():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚽ Mini Futbol", callback_data="field_futbol")],
        [InlineKeyboardButton(text="🏐 Voleybol", callback_data="field_voleybol")],
        [InlineKeyboardButton(text="📋 Mening bronlarim", callback_data="my_bookings")],
    ])
    return keyboard

@dp.message(CommandStart())
async def start(message: Message):
    await message.answer(
        f"⚽ Xush kelibsiz, {message.from_user.first_name}!\n\n"
        "🏟 O'yingoh — maydon bron qilish botiga xush kelibsiz!\n\n"
        "Qaysi maydonni bron qilmoqchisiz?",
        reply_markup=main_menu()
    )

@dp.callback_query(F.data == "field_futbol")
async def futbol_info(callback: CallbackQuery):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📅 Bron qilish", callback_data="book_futbol")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_main")],
    ])
    await callback.message.edit_text(
        "⚽ Mini Futbol Maydon\n\n"
        "📍 19-maktab yonida\n"
        "🕐 Ish vaqti: 05:00 - 23:00\n"
        "💰 Narx: 140,000 so'm/soat\n"
        "🌧 Usti yopiq\n\n"
        "Bron qilishni xohlaysizmi?",
        reply_markup=keyboard
    )

@dp.callback_query(F.data == "field_voleybol")
async def voleybol_info(callback: CallbackQuery):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📅 Bron qilish", callback_data="book_voleybol")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_main")],
    ])
    await callback.message.edit_text(
        "🏐 Voleybol Maydoni\n\n"
        "📍 19-maktab yonida\n"
        "🕐 Ish vaqti: 05:00 - 23:00\n"
        "💰 Narx: 60,000 so'm/soat\n\n"
        "Bron qilishni xohlaysizmi?",
        reply_markup=keyboard
    )

@dp.callback_query(F.data == "back_main")
async def back_main(callback: CallbackQuery):
    await callback.message.edit_text(
        "Qaysi maydonni bron qilmoqchisiz?",
        reply_markup=main_menu()
    )

@dp.callback_query(F.data == "my_bookings")
async def my_bookings(callback: CallbackQuery):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_main")],
    ])
    await callback.message.edit_text(
        "📋 Sizning bronlaringiz\n\n"
        "Hozircha aktiv bron yo'q.",
        reply_markup=keyboard
    )
@dp.callback_query(F.data == "book_futbol")
async def book_futbol(callback: CallbackQuery):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_main")],
    ])
    await callback.message.edit_text(
        "✅ Arizangiz qabul qilindi!\n\n"
        "⚽ Mini Futbol Maydon\n"
        "📍 19-maktab yonida\n\n"
        "Tez orada siz bilan bog'lanamiz.",
        reply_markup=keyboard
    )

@dp.callback_query(F.data == "book_voleybol")
async def book_voleybol(callback: CallbackQuery):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_main")],
    ])
    await callback.message.edit_text(
        "✅ Arizangiz qabul qilindi!\n\n"
        "🏐 Voleybol Maydoni\n"
        "📍 19-maktab yonida\n\n"
        "Tez orada siz bilan bog'lanamiz.",
        reply_markup=keyboard
    )    
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

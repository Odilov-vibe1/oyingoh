import os
import asyncio
import logging
from fastapi import FastAPI
import uvicorn
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo

# 1. Logging sozlmalari
logging.basicConfig(level=logging.INFO)

# 2. Muhit o'zgaruvchilarini olish
BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBAPP_URL = os.getenv("WEBAPP_URL", "https://t me") # Mini App manzili

# 3. Bot va Dispatcher yaratish
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
app = FastAPI()

# ----------------------------------------------------
# 4. TELEGRAM BOT MANTIQI
# ----------------------------------------------------
@dp.message(CommandStart())
async def start_handler(message: types.Message):
    # Mini App tugmasini yaratish
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="⚽ Maydon bron qilish (Oyingoh)",
                    web_app=WebAppInfo(url=WEBAPP_URL)
                )
            ]
        ]
    )
    
    await message.answer(
        f"Salom, {message.from_user.first_name}! 👋\n\n"
        f"'Oyingoh' platformasiga xush kelibsiz. Mini-futbol va voleybol maydonlarini osongina bron qiling!",
        reply_markup=keyboard
    )

# ----------------------------------------------------
# 5. FASTAPI REST API ENDPOINT'LARI (Mini App uchun)
# ----------------------------------------------------
@app.get("/")
async def root():
    return {"status": "ok", "message": "Oyingoh Python Backend serveri ishlamoqda! 🚀"}

@app.get("/api/stadiums")
async def get_stadiums():
    # Bu yerga kelajakda bazadan maydonlarni olib beruvchi kod yoziladi
    return [
        {
            "id": 1,
            "name": "Chilanzar Stadium",
            "sport": "Football",
            "price_per_hour": 140000,
            "has_shower": True
        }
    ]

# ----------------------------------------------------
# 6. SERVER VA BOTNI BIR VAQTDA ISHGA TUSHIRISH
# ----------------------------------------------------
async def start_services():
    # Botni fonda ishga tushirish (Polling)
    asyncio.create_task(dp.start_polling(bot))
    
    # Render bergan PORT da FastAPI serverini ishga tushirish
    port = int(os.getenv("PORT", 8000))
    config = uvicorn.Config(app, host="0.0.0.0", port=port, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()

if __name__ == "__main__":
    asyncio.run(start_services())

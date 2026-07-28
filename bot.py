require("dotenv").config();
const express = require("express");
const cors = require("cors");
const { Bot } = require("grammy");
const { PrismaClient } = require("@prisma/client");
const crypto = require("crypto");

// 1. Initsializatsiya
const app = express();
const prisma = new PrismaClient();
const bot = new Bot(process.env.BOT_TOKEN);
const PORT = process.env.PORT || 3000;

// Middleware'lar
app.use(cors());
app.use(express.json());

// ----------------------------------------------------
// 2. TELEGRAM BOT MANTIQI
// ----------------------------------------------------
bot.command("start", async (ctx) => {
  const webAppUrl = process.env.WEBAPP_URL;

  await ctx.reply(
    `Salom, ${ctx.from.first_name}! 👋\n\n` +
    `"Oyingoh" platformasiga xush kelibsiz. Mini-futbol va voleybol maydonlarini osongina va tez bron qiling!`,
    {
      reply_markup: {
        inline_keyboard: [
          [
            {
              text: "⚽ Maydon bron qilish (Oyingoh)",
              web_app: { url: webAppUrl }
            }
          ]
        ]
      }
    }
  );
});

// Botni fonda ishga tushirish (Long Polling)
bot.start().catch((err) => console.error("Botda xatolik:", err));

// ----------------------------------------------------
// 3. XAVFSIZLIK MIDDLEWARE (Telegram initData validsiyasi)
// ----------------------------------------------------
function verifyTelegramData(req, res, next) {
  const initData = req.headers["x-telegram-init-data"];
  
  // Agarda rivojlantirish (development) rejimida bo'lsangiz tekshiruvni o'tkazib yuborishingiz mumkin
  if (!initData && process.env.NODE_ENV === "development") {
    return next();
  }

  if (!initData) {
    return res.status(401).json({ error: "Avtorizatsiyadan o'tilmagan!" });
  }

  try {
    const urlParams = new URLSearchParams(initData);
    const hash = urlParams.get("hash");
    urlParams.delete("hash");

    const paramsToSign = Array.from(urlParams.entries())
      .map(([key, value]) => `${key}=${value}`)
      .sort()
      .join("\n");

    const secretKey = crypto
      .createHmac("sha256", "WebAppData")
      .update(process.env.BOT_TOKEN)
      .digest();

    const signature = crypto
      .createHmac("sha256", secretKey)
      .update(paramsToSign)
      .digest("hex");

    if (signature === hash) {
      // Telegram foydalanuvchi ma'lumotlarini req.tgUser ichiga joylaymiz
      const user = JSON.parse(urlParams.get("user"));
      req.tgUser = user;
      return next();
    } else {
      return res.status(403).json({ error: "Ma'lumotlar buzilgan yoki soxta!" });
    }
  } catch (error) {
    return res.status(400).json({ error: "Validsiyada xatolik yuz berdi" });
  }
}

// ----------------------------------------------------
// 4. REST API ENDPOINT'LARI (Mini App uchun)
// ----------------------------------------------------

// Health check (Render server holatini tekshirish uchun)
app.get("/", (req, res) => {
  res.send("Oyingoh Backend API va Bot muvaffaqiyatli ishlamoqda! 🚀");
});

// A) Barcha maydonlar ro'yxatini olish
app.get("/api/stadiums", async (req, res) => {
  try {
    const stadiums = await prisma.stadium.findMany({
      include: { owner: true }
    });
    res.json(stadiums);
  } catch (error) {
    res.status(500).json({ error: "Maydonlarni yuklashda xatolik" });
  }
});

// B) Bitta maydon ma'lumotlarini olish
app.get("/api/stadiums/:id", async (req, res) => {
  try {
    const { id } = req.params;
    const stadium = await prisma.stadium.findUnique({
      where: { id },
      include: { bookings: true }
    });
    
    if (!stadium) {
      return res.status(404).json({ error: "Maydon topilmadi" });
    }

    res.json(stadium);
  } catch (error) {
    res.status(500).json({ error: "Xatolik yuz berdi" });
  }
});

// C) Yangi bron yaratish (Booking)
app.post("/api/bookings", verifyTelegramData, async (req, res) => {
  try {
    const { stadiumId, bookingDate, startTime, endTime, totalPrice } = req.body;
    const tgUser = req.tgUser;

    // 1. Foydalanuvchini bazadan izlash yoki yangi yaratish
    let user = await prisma.user.findUnique({
      where: { telegramId: BigInt(tgUser.id) }
    });

    if (!user) {
      user = await prisma.user.create({
        data: {
          telegramId: BigInt(tgUser.id),
          firstName: tgUser.first_name,
          lastName: tgUser.last_name || null,
          username: tgUser.username || null
        }
      });
    }

    // 2. Vaqt band emasligini tekshirish (Overbooking'ning oldini olish)
    const existingBooking = await prisma.booking.findFirst({
      where: {
        stadiumId,
        bookingDate: new Date(bookingDate),
        startTime,
        status: { in: ["PENDING", "CONFIRMED"] }
      }
    });

    if (existingBooking) {
      return res.status(400).json({ error: "Ushbu vaqt allaqachon band qilingan!" });
    }

    // 3. Bronni saqlash
    const newBooking = await prisma.booking.create({
      data: {
        userId: user.id,
        stadiumId,
        bookingDate: new Date(bookingDate),
        startTime,
        endTime,
        totalPrice,
        status: "CONFIRMED"
      }
    });

    // 4. Foydalanuvchiga Telegram bot orqali tasdiq xabarini yuborish
    await bot.api.sendMessage(
      tgUser.id,
      `✅ **Broningiz tasdiqlandi!**\n\n` +
      `📅 Sana: ${bookingDate}\n` +
      `⏰ Vaqt: ${startTime} - ${endTime}\n` +
      `💰 Summa: ${totalPrice} so'm\n\n` +
      `Oyingoh xizmatidan foydalanganingiz uchun rahmat!`
    );

    res.status(201).json(newBooking);
  } catch (error) {
    console.error("Bron xatoligi:", error);
    res.status(500).json({ error: "Bron qilishda xatolik yuz berdi" });
  }
});

// ----------------------------------------------------
// 5. SERVERNI ISHGA TUSHIRISH
// ----------------------------------------------------
app.listen(PORT, () => {
  console.log(`Oyingoh serveri ${PORT}-portda ishga tushdi...`);
});

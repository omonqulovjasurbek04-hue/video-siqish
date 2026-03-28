# 🎬 VideoBot – Video Siqish Telegram Boti

**Aiogram 3** + **FFmpeg** asosida qurilgan to'liq funksional video siqish Telegram boti.

---

## 🚀 O'rnatish

### 1. Muhit o'rnatilganligini tekshiring
```bash
python --version   # Python 3.10+
ffmpeg -version    # FFmpeg o'rnatilgan bo'lsin
```

> ❗ FFmpeg o'rnatilmagan bo'lsa: https://ffmpeg.org/download.html

### 2. Virtual muhit va paketlar
```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install aiogram python-dotenv
```

### 3. Bot tokenini sozlash
`.env` faylini oching va tokeningizni kiriting:
```
BOT_TOKEN=1234567890:ABCdef...
```
> Token olish: [@BotFather](https://t.me/BotFather) → `/newbot`

### 4. Ishga tushirish
```bash
.venv\Scripts\python.exe main.py
```

---

## 📖 Bot imkoniyatlari

| Funksiya | Tavsif |
|---|---|
| 🎥 Video qabul qilish | MP4, MOV, MKV, AVI, WEBM, FLV |
| 🔍 Tahlil | Format, hajm, davomiylik, FPS, kodek |
| 🗜 Kengaytirilgan siqish | CRF 32, 64k audio, 720p |
| ⚖️ O'rta siqish | CRF 24, 128k audio, 1080p |
| 🪶 Minimal siqish | CRF 18, 192k audio, asl ruxsat |
| 📱 Platform profillari | Instagram, TikTok, YouTube, Twitter |
| ⚙️ Maxsus sozlamalar | CRF, FPS, audio sifati, ruxsat |
| 📊 Real-time progress | Joylash vaqtida foiz ko'rsatkich |
| 💾 Avto cleanup | Fayllar siqishdan keyin o'chiriladi |

---

## 💬 Bot buyruqlari

| Buyruq | Tavsif |
|---|---|
| `/start` | Botni ishga tushirish |
| `/help` | Qo'llanma |
| `/cancel` | Jarayonni bekor qilish |

---

## 🗂 Loyiha tuzilmasi

```
pythonProject3/
├── main.py            ← Asosiy bot fayli
├── .env               ← BOT_TOKEN
├── bot_uploads/       ← Yuklangan videolar (avtomatik tozalanadi)
├── bot_outputs/       ← Siqilgan videolar (avtomatik tozalanadi)
└── requirements.txt
```

---

## 📦 Talablar

```
aiogram>=3.0
python-dotenv
ffmpeg (tizimda o'rnatilgan bo'lishi kerak)
```

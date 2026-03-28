# 🎬 VideoBot — Telegram Video Qayta Ishlash Boti

Telegram bot — videolarni siqish, kesish, birlashtirish, watermark qo'shish va GIF yaratish uchun.

## ✨ Imkoniyatlar

| Buyruq | Tavsif |
|--------|--------|
| `/start` | Botni ishga tushirish |
| `/help` | Yordam va qo'llanma |
| `/trim` | ✂️ Video kesish (qirqish) |
| `/merge` | 🔗 2 ta videoni birlashtirish |
| `/watermark` | 💧 Watermark matn qo'shish |
| `/gif` | 🎞 GIF yaratish / Screenshot olish |
| `/cancel` | ❌ Jarayonni bekor qilish |

**Siqish:** Video yuboring → 3 xil daraja (Kengaytirilgan, O'rta, Minimal) yoki platforma profili tanlang.

**Tezkor asboblar:** Video yuborilgandan keyin menyudan — 🗜 Siqish, ✨ Sifat, 📐 O'lcham, 🎬 FPS, 🔊 Ovoz, 📊 Ma'lumot.

**Platformalar:** Instagram, TikTok, YouTube, Twitter/X — optimal sozlamalar avtomatik.

**Formatlar:** MP4, MOV, MKV, AVI, WEBM, FLV

---

## 🚀 O'rnatish va Ishga tushirish

Loyihani lokal kompyuterda yoki Docker orqali serverda (Railway, Render, VPS) ishga tushirishingiz mumkin. Bot mukammal ishlashi uchun tizimda **FFmpeg** o'rnatilgan bo'lishi shart.

### 1-usul: Lokal kompyuterda (Oddiy usul)

1. **FFmpeg o'rnatish (ENG MUHIM!)**
   * Linux (Ubuntu/Debian): `sudo apt update && sudo apt install ffmpeg -y`
   * macOS: `brew install ffmpeg`
   * Windows: FFmpeg ni rasmiy saytdan yuklab olib, PATH ga qo'shing.

2. **Loyihani klonlash va papkaga kirish**
   ```bash
   git clone https://github.com/YOUR_USERNAME/video-siqish.git
   cd video-siqish
   ```

3. **Kutubxonalarni o'rnatish**
   ```bash
   pip install -r requirements.txt
   ```

4. **Bot tokenini sozlash**
   `.env.example` faylidan nusxa olib, tokeningizni kiriting:
   ```bash
   cp .env.example .env
   nano .env
   ```
   ```env
   BOT_TOKEN=1234567890:AABBCCyour_token_here
   ```

5. **Botni ishga tushirish**
   ```bash
   python3 main.py
   ```

---

### 2-usul: Docker yordamida (Server yoki Local)

Loyiha uchun tayyor `Dockerfile` mavjud. U avtomatik ravishda FFmpeg va barcha kutubxonalarni o'rnatadi.

1. `.env` faylini yuqoridagidek yarating va `BOT_TOKEN` ni kiriting.
2. Docker imageni yig'ish (build):
   ```bash
   docker build -t videobot .
   ```
3. Konteynerni fonda ishga tushirish:
   ```bash
   docker run -d --name tg-videobot --env-file .env videobot
   ```

**Docker Compose bilan:**
```bash
docker-compose up -d
```

---

### 3-usul: Railway.app (Bulutli platforma)

Loyihada Railway uchun maxsus konfiguratsiyalar sozlangan.

1. [Railway.app](https://railway.app/) saytida ro'yxatdan o'ting.
2. **New Project** → **Deploy from GitHub repo** tanlang.
3. **Variables** bo'limiga `BOT_TOKEN` ni qo'shing.
4. Railway avtomatik ravishda deploy qiladi.

---

## ⚙️ Texnik talablar

| Talab | Minimal |
|-------|---------|
| RAM | 2 GB (5 GB tavsiya) |
| Disk | 20 GB bo'sh joy |
| Python | 3.10+ |
| FFmpeg | 4.0+ |
| OS | Ubuntu 20.04+ / Debian 11+ / Windows / macOS |

---

## 📁 Loyiha tuzilishi

```
video-siqish/
├── main.py              # Bot ishga tushirish (entry point)
├── config.py            # Sozlamalar va konstantalar
├── states.py            # FSM state guruhlari
├── keyboards.py         # Barcha klaviaturalar (menyu)
├── server.py            # Health check HTTP server
├── handlers/
│   ├── __init__.py      # Router registratsiya
│   ├── start.py         # /start, /help, /cancel
│   ├── compress.py      # Video siqish
│   ├── trim.py          # /trim — video kesish
│   ├── merge.py         # /merge — birlashtirish
│   ├── watermark.py     # /watermark — matn qo'shish
│   ├── gif.py           # /gif — GIF / Screenshot
│   ├── tools.py         # Tezkor asboblar (/siq, /sifat, /olcham, /fps, /ovoz, /info)
│   └── fallback.py      # Fallback handlerlar
├── utils/
│   ├── __init__.py      # Utils eksportlar
│   ├── ffmpeg.py        # FFmpeg helper funksiyalar
│   ├── formatters.py    # Hajm, vaqt formatlash
│   └── cleanup.py       # Fayl tozalash va scheduler
├── requirements.txt     # Python kutubxonalar
├── Dockerfile           # Docker image
├── docker-compose.yml   # Docker Compose
├── railway.json         # Railway config
├── .env                 # Bot tokeni (maxfiy, gitignore'da)
├── .env.example         # Namuna .env fayli
├── .gitignore           # Git ignore
├── bot_uploads/         # Yuklangan videolar (vaqtinchalik)
└── bot_outputs/         # Qayta ishlangan videolar (vaqtinchalik)
```

## 📝 Litsenziya

MIT License

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

**Platformalar:** Instagram, TikTok, YouTube, Twitter/X — optimal sozlamalar avtomatik.

**Formatlar:** MP4, MOV, MKV, AVI, WEBM, FLV

---

## 🚀 Serverga o'rnatish

### 1. Serverni yangilash
```bash
sudo apt update && sudo apt upgrade -y
```

### 2. Python o'rnatish
```bash
sudo apt install python3 python3-pip python3-venv -y
```

### 3. FFmpeg o'rnatish (ENG MUHIM!)
```bash
sudo apt install ffmpeg -y
```

Tekshirish:
```bash
ffmpeg -version
ffprobe -version
```

### 4. Loyihani klonlash
```bash
git clone https://github.com/YOUR_USERNAME/video-siqish.git
cd video-siqish
```

### 5. Kutubxonalar o'rnatish
```bash
pip install -r requirements.txt
```

### 6. Bot tokenini sozlash
`.env` faylini oching va tokenni kiriting:
```bash
nano .env
```
```
BOT_TOKEN=1234567890:AABBCCyour_token_here
```

### 7. Botni ishga tushirish
```bash
python3 main.py
```

---

## 🔄 Systemd — Bot doim ishlashi uchun

Server qayta yoqilganda ham bot avtomatik ishga tushadi.

### Service fayli yaratish:
```bash
sudo nano /etc/systemd/system/videobot.service
```

Fayl ichiga yozing:
```ini
[Unit]
Description=VideoBot - Telegram Video Bot
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/video-siqish
ExecStart=/usr/bin/python3 main.py
EnvironmentFile=/home/ubuntu/video-siqish/.env
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### Xizmatni yoqish:
```bash
sudo systemctl daemon-reload
sudo systemctl enable videobot
sudo systemctl start videobot
```

### Tekshirish:
```bash
sudo systemctl status videobot   # Yashil = ishlayapti ✅
```

### Boshqa buyruqlar:
```bash
sudo systemctl stop videobot     # To'xtatish
sudo systemctl restart videobot  # Qayta ishga tushirish
sudo journalctl -u videobot -f   # Loglarni ko'rish
```

---

## ⚙️ Texnik talablar

| Talab | Minimal |
|-------|---------|
| RAM | 2 GB (5 GB tavsiya) |
| Disk | 20 GB bo'sh joy |
| Python | 3.10+ |
| FFmpeg | 4.0+ |
| OS | Ubuntu 20.04+ / Debian 11+ |

---

## 📁 Loyiha tuzilishi

```
video-siqish/
├── main.py            # Asosiy bot kodi
├── requirements.txt   # Python kutubxonalar
├── .env               # Bot tokeni (maxfiy)
├── .gitignore         # Git ignore
├── README.md          # Hujjat
├── bot_uploads/       # Yuklangan videolar (vaqtinchalik)
└── bot_outputs/       # Qayta ishlangan videolar (vaqtinchalik)
```

## 📝 Litsenziya

MIT License

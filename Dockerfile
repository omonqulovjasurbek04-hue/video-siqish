FROM python:3.11-slim

# FFmpeg o'rnatish (bir martalik, tozalangan)
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Ishchi papka
WORKDIR /app

# Kutubxonalar o'rnatish (cache layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Loyiha fayllarini ko'chirish
COPY . .

# Vaqtinchalik papkalar yaratish
RUN mkdir -p bot_uploads bot_outputs

# Non-root user (xavfsizlik)
RUN useradd -m botuser && \
    chown -R botuser:botuser /app
USER botuser

# Railway PORT
ENV PORT=8080

CMD ["python3", "main.py"]
FROM python:3.11-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*


COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN apt-get update && apt-get install -y ffmpeg
COPY . .
# Railway PORT ni talab qiladi (bot uchun shart emas, lekin u kutishi mumkin)
ENV PORT=8080
CMD ["python3", "main.py"]
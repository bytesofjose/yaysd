FROM python:3.11-slim-bookworm

# Explicitly use noninteractive frontend
ENV DEBIAN_FRONTEND=noninteractive

# Update and install ffmpeg + nodejs (JS runtime for yt-dlp format extraction)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    nodejs \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Create logs directory
RUN mkdir -p /app/logs

EXPOSE 8000

CMD ["python", "-m", "app.main"]

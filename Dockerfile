FROM python:3.11-slim-bookworm

# Explicitly use noninteractive frontend
ENV DEBIAN_FRONTEND=noninteractive

<<<<<<< HEAD
# Update and install ffmpeg + nodejs (JS runtime for yt-dlp format extraction)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    nodejs \
=======
# Update and install ffmpeg with retries and verbose output to diagnose failures
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
>>>>>>> ed76a6993d95e6e0ce87e137bae0a38c8ff30b7d
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Create logs directory
RUN mkdir -p /app/logs

EXPOSE 8000

CMD ["python", "-m", "app.main"]

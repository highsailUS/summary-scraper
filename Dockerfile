FROM python:3.10-slim

# Install system dependencies + Playwright dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    ca-certificates \
    gnupg \
    libnss3 \
    libxss1 \
    libasound2 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libgbm1 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libxshmfence1 \
    fonts-liberation \
    libu2f-udev \
    xvfb \
    # Playwright recommended extra deps
    libgtk-3-0 \
    libx11-xcb1 \
    libxext6 \
    libxi6 \
    libxtst6 \
    libglib2.0-0 \
    libfontconfig1 \
    libharfbuzz0b \
    libfreetype6 \
    libjpeg62-turbo \
    libpng16-16 \
    libwebp7 \
    libenchant-2-2 \
    shared-mime-info \
    --no-install-recommends && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers
RUN python -m playwright install --with-deps chromium

COPY app ./app

ENV PORT=8080

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]

FROM python:3.12-slim

# Dependencias del sistema para Playwright + Chromium
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl wget gnupg ca-certificates \
    libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 \
    libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 \
    libgbm1 libasound2 libpango-1.0-0 libpangocairo-1.0-0 \
    libgtk-3-0 libx11-xcb1 libxcb-dri3-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Instalar el navegador de Playwright
RUN playwright install chromium --with-deps

COPY . .

# El CV y la DB viven en un volumen externo; crear los dirs como placeholder
RUN mkdir -p /data/cover_letters /data/tailored_cvs

VOLUME ["/data"]

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DATA_DIR=/data

CMD ["python", "daily_scrape.py"]

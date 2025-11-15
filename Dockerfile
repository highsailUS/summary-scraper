# Use official Playwright image with browsers preinstalled
FROM mcr.microsoft.com/playwright/python:v1.45.0-jammy

WORKDIR /app

# Install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app
COPY app ./app

# Expose port (Railway sets $PORT)
ENV PYTHONUNBUFFERED=1

CMD ["bash", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]


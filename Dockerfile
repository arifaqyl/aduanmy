FROM mcr.microsoft.com/playwright/python:v1.49.0-jammy

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ADUANMY_PROJECT_ROOT=/app \
    ADUANMY_DB_PATH=/data/aduanmy.db \
    ADUANMY_DATA_DIR=/data \
    ADUANMY_THREADS_SESSION_PATH=/data/private/threads-session.json \
    ADUANMY_AUTO_REFRESH_ENABLED=true \
    ADUANMY_FULL_REFRESH_INTERVAL_SECONDS=900 \
    ADUANMY_GTFS_ANOMALY_ENABLED=false \
    ADUANMY_GTFS_REFRESH_INTERVAL_SECONDS=300 \
    ADUANMY_DASHBOARD_POLL_INTERVAL_SECONDS=300 \
    ADUANMY_REFRESH_ON_STARTUP=true \
    ADUANMY_RETENTION_DAYS=90

COPY requirements.production.txt ./
RUN pip install --no-cache-dir -r requirements.production.txt

COPY pyproject.toml README.md LICENSE ./
COPY app ./app
COPY configs ./configs
COPY static ./static
COPY scripts ./scripts

RUN mkdir -p /data

VOLUME ["/data"]
EXPOSE 8000

HEALTHCHECK --interval=60s --timeout=10s --start-period=90s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health/live', timeout=8)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips=*"]

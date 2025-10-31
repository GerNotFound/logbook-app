# syntax=docker/dockerfile:1
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN useradd -u 10001 -m appuser
USER appuser

EXPOSE 8000
ENV LOG_LEVEL=INFO

CMD ["bash", "-lc", "gunicorn --workers ${GUNICORN_WORKERS:-2} --threads ${GUNICORN_THREADS:-1} --timeout ${GUNICORN_TIMEOUT:-30} --bind 0.0.0.0:${PORT:-8000} app:create_app()"]

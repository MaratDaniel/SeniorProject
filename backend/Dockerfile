# API, scheduler worker and migrations share this image.
# Pin the base image by digest before deploying anywhere public.
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app
COPY requirements.txt .
RUN pip install --require-hashes -r requirements.txt

COPY alembic.ini ./
COPY migrations ./migrations
COPY app ./app
COPY demo ./demo

RUN useradd --system --uid 10001 --home-dir /app adal \
    && mkdir -p /app/media \
    && chown adal /app/media
USER adal

EXPOSE 8000
# Only the web container can reach this port, so forwarded headers from it are trusted.
CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", \
     "--proxy-headers", "--forwarded-allow-ips", "*", "--ws-max-size", "65536"]

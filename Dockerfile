# Demo image: runs on generated data by default, so a public instance never
# re-serves Yahoo's feed or needs an API key. Override BLOOMTERM_PROVIDER to
# "yahoo" (plus FINNHUB_API_KEY) for a private, real-data instance.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    BLOOMTERM_PROVIDER=mock

WORKDIR /srv

COPY pyproject.toml README.md ./
COPY app ./app
RUN pip install --no-cache-dir .

EXPOSE 8420

# Render and Fly both inject PORT; fall back to the local default.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8420}"]

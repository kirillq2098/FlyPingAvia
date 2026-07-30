FROM python:3.12-slim

WORKDIR /app

# Non-root user for production-safe runtime
RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin appuser

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY flypingavia ./flypingavia
COPY pyproject.toml README.md ./

RUN mkdir -p /app/data && chown -R appuser:appuser /app

ENV PYTHONUNBUFFERED=1
ENV DATABASE_URL=sqlite+aiosqlite:///./data/flypingavia.db
ENV WEBAPP_HOST=0.0.0.0
ENV WEBAPP_PORT=8080
# Do not bake WEBAPP_URL / tokens into the image — pass via env / compose.
ENV APP_ENV=production
ENV WEBAPP_DEV_USER_ID=0
ENV FORWARDED_ALLOW_IPS=127.0.0.1

USER appuser

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/api/health', timeout=3)"

CMD ["python", "-m", "flypingavia"]

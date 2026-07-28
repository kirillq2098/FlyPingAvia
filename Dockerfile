FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY flypingavia ./flypingavia
COPY pyproject.toml README.md ./

RUN mkdir -p /app/data

ENV DATABASE_URL=sqlite+aiosqlite:///./data/flypingavia.db
ENV PYTHONUNBUFFERED=1

CMD ["python", "-m", "flypingavia"]

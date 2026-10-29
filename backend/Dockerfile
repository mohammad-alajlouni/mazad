FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN apt-get update && apt-get install -y --no-install-recommends libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0 fonts-dejavu-core fonts-noto-core && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN useradd --create-home app && mkdir -p /app/storage && chown -R app:app /app
USER app
EXPOSE 8000
# Several worker processes (WEB_CONCURRENCY, 3 unless .env says otherwise):
# rendering a preview or a booklet is CPU work that would otherwise hold up
# every other request (opening the dashboard, a project, saving).
CMD ["sh","-c","alembic upgrade head && python -m app.bootstrap && exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers ${WEB_CONCURRENCY:-3}"]

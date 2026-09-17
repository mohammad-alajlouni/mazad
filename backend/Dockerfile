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
CMD ["sh","-c","alembic upgrade head && python -m app.bootstrap && uvicorn app.main:app --host 0.0.0.0 --port 8000"]

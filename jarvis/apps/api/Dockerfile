FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app

COPY pyproject.toml README.md* ./
COPY src ./src
COPY alembic.ini ./

RUN pip install --no-cache-dir -e ".[postgres,redis]"

EXPOSE 8000
CMD ["uvicorn", "jarvis.main:app", "--host", "0.0.0.0", "--port", "8000"]

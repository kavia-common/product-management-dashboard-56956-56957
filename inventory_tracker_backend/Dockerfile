# syntax=docker/dockerfile:1

FROM python:3.11-slim AS runtime

# Prevents Python from writing .pyc files and buffers (better logs in docker)
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# System deps (kept minimal). libpq is commonly needed by Postgres clients.
RUN apt-get update -y \
  && apt-get install -y --no-install-recommends libpq5 \
  && rm -rf /var/lib/apt/lists/*

# Install Python deps first to leverage Docker layer caching.
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy application code
COPY src /app/src

EXPOSE 8000

# Note:
# - DATABASE_URL is supplied by docker-compose.yml
# - App import path is src.api.main:app
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]

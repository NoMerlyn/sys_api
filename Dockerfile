FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# System deps for asyncpg + cryptography wheels
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps separately for better layer caching
# Copy source first so editable install can find the `app/` package
COPY app ./app
COPY alembic ./alembic
COPY pyproject.toml ./
RUN pip install --upgrade pip && pip install -e ".[dev]"

# Copy remaining source
COPY alembic.ini ./
COPY tests ./tests

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
# Stage 1: Build dependencies
FROM python:3.11-slim AS builder

WORKDIR /app

# build dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

# copy dependency files
COPY pyproject.toml uv.lock ./

# install dependencies in virtual environment
RUN uv sync --frozen --no-dev

# Stage 2: Runtime
FROM python:3.11-slim

WORKDIR /app

# install only runtime dependencies
RUN apt-get update && apt-get install -y \
    libsndfile1 ffmpeg libmagic1 curl \
    && rm -rf /var/lib/apt/lists/*

# copy virtual environment from builder
COPY --from=builder /app/.venv /app/.venv

# copy application code
COPY src/ ./src/

RUN mkdir -p uploads data model_cache

# Non-root user
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app
USER appuser

# add venv to PATH
ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]

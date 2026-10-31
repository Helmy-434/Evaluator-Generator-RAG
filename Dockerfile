# syntax=docker/dockerfile:1
FROM python:3.11-slim

WORKDIR /app

# 1. System dependencies layer
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# 2. Copy dependencies definition FIRST (maximizes Docker layer cache)
COPY requirements.txt .

# 3. Mount pip cache so downloaded wheels persist across Docker builds
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.txt

# 4. Copy project source files LAST so code edits don't invalidate pip layers
COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
FROM python:3.11-slim

# Minimal build for MCP Gateway
WORKDIR /app

# system deps for psycopg2 and docker SDK
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    gcc \
    libffi-dev \
    git \
  && rm -rf /var/lib/apt/lists/*

# copy requirements first to leverage layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# copy app
COPY . /app

EXPOSE 8080
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8080"]

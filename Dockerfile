FROM python:3.11-slim

# Minimal build for MCP Gateway
WORKDIR /app

# system deps for psycopg2, docker SDK, and LibreOffice headless
# (libreoffice-* is needed by the office_convert tool, e.g. export to PDF)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    gcc \
    libffi-dev \
    git \
    libreoffice-writer \
    libreoffice-calc \
    libreoffice-impress \
  && rm -rf /var/lib/apt/lists/*

# copy requirements first to leverage layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# copy app
COPY . /app

# Run as an unprivileged user. Writable runtime state (audit log, office
# output) lives under /data so a read-only /app bind-mount doesn't break it.
RUN useradd --create-home --uid 10001 app \
  && mkdir -p /data/output \
  && chown -R app:app /app /data
USER app

ENV AUDIT_LOG_PATH=/data/audit.log \
    OFFICE_OUTPUT_DIR=/data/output

EXPOSE 8080

# Liveness probe (no auth required); pure-stdlib so no extra packages needed.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD ["python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8080/health/live', timeout=4).status==200 else 1)"]

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8080"]

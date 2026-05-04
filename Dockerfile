# ── Build stage (install deps) ──────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /install

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install/pkg -r requirements.txt


# ── Runtime stage ────────────────────────────────────────────────────
FROM python:3.11-slim

LABEL maintainer="drop-report"
LABEL description="Dashboard operativo de dropshipping"

# Non-root user for security
RUN addgroup --system app && adduser --system --ingroup app app

WORKDIR /dropreport

# Copy installed packages from builder
COPY --from=builder /install/pkg /usr/local

# Copy application code
COPY app/       ./app/
COPY frontend/  ./frontend/

# Data volume (SQLite lives here — persists across restarts)
RUN mkdir -p /data && chown app:app /data
VOLUME ["/data"]

# Switch to non-root
USER app

EXPOSE 8000

# Uvicorn: 1 worker on RPi (limited RAM), adjust via env WORKERS
ENV WORKERS=1 \
    DB_PATH=/data/dropreport.db \
    SECRET_KEY=changeme-in-production \
    ADMIN_USER=admin \
    ADMIN_PASS=dropi2024

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers ${WORKERS}"]

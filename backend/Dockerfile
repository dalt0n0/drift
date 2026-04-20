# syntax=docker/dockerfile:1
FROM python:3.11-slim AS builder

WORKDIR /build
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Runtime ────────────────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

# Non-root user
RUN groupadd -r -g 1000 drift && useradd -r -u 1000 -g drift -s /sbin/nologin drift

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application
COPY --chown=drift:drift . .

# Runtime directories
RUN mkdir -p /var/Drift/audit /var/Drift/uploads && \
    chown -R drift:drift /var/Drift

USER drift

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')" || exit 1

CMD ["gunicorn", "app.main:app", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--workers", "4", \
     "--bind", "0.0.0.0:8000", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "--timeout", "120"]

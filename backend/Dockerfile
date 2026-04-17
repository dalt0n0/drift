FROM python:3.11-slim-bookworm AS base

# Security: non-root user
RUN groupadd -r drift && useradd -r -g drift -d /app -s /sbin/nologin drift

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    libmagic1 \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps as root before dropping privileges
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copy source
COPY --chown=drift:drift . .

# Upload dir
RUN mkdir -p /var/drift/uploads /var/drift/logs \
    && chown -R drift:drift /var/drift

USER drift

EXPOSE 8000

CMD ["uvicorn", "app.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "4", \
     "--proxy-headers", \
     "--forwarded-allow-ips", "*", \
     "--access-log", \
     "--log-level", "warning"]

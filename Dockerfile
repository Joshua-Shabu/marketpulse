# MarketPulse — production container image
# Multi-stage build: install deps in a builder layer, copy only what's needed into a slim runtime image.

FROM python:3.11-slim AS builder

WORKDIR /build

# System deps needed to build any wheels that require compilation (pandas, etc.)
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


FROM python:3.11-slim AS runtime

WORKDIR /app

# Copy installed packages from the builder stage
COPY --from=builder /install /usr/local

# Copy application code only (not tests, .env, etc. — see .dockerignore)
COPY app/ ./app/

# Run as a non-root user
RUN useradd --create-home --shell /bin/bash appuser
USER appuser

EXPOSE 8000

# Basic container healthcheck against FastAPI's auto-generated docs route
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/docs')" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

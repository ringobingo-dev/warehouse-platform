# Stage 1: Builder
FROM python:3.11-slim as builder

# Install build dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Set work directory for build
WORKDIR /build

# Install Python dependencies
COPY requirements.txt .
RUN pip wheel --no-cache-dir --no-deps --wheel-dir /build/wheels -r requirements.txt

# Stage 2: Runtime
FROM python:3.11-slim

# Create non-root user
RUN useradd -m -U -s /bin/false appuser

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/home/appuser/.local/bin:$PATH" \
    WAREHOUSE_SERVICE_PORT=8000

# Install runtime dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Set work directory
WORKDIR /app

# Copy wheels from builder
COPY --from=builder /build/wheels /wheels

# Install dependencies
RUN pip install --no-cache-dir /wheels/* \
    && rm -rf /wheels

# Copy application code
COPY . .

# Set ownership and permissions
RUN chown -R appuser:appuser /app \
    && chmod -R 755 /app

# Switch to non-root user
USER appuser

# Expose port
EXPOSE $WAREHOUSE_SERVICE_PORT

# Configure healthcheck
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:$WAREHOUSE_SERVICE_PORT/health || exit 1

# Set entry point
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", \
    "--workers", "4", "--log-level", "info", \
    "--access-log", "--proxy-headers"]


# ── Stage 1: Builder ─────────────────────────────────────
# Install dependencies in a separate stage to keep final image small
FROM python:3.10-slim AS builder

WORKDIR /app

# Install build tools needed by some Python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Pre-download the HuggingFace embedding model during build
# so the container starts instantly without downloading at runtime
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"


# ── Stage 2: Runtime ──────────────────────────────────────
FROM python:3.10-slim AS runtime

# Don't write .pyc files, stream logs immediately
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Create a non-root user for security
RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser

WORKDIR /app

# Copy installed packages from builder stage
COPY --from=builder /usr/local/lib/python3.10/site-packages /usr/local/lib/python3.10/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy HuggingFace model cache from builder
COPY --from=builder /root/.cache /home/appuser/.cache

# Copy application source
COPY --chown=appuser:appgroup . .

# Create directories the app writes to at runtime
RUN mkdir -p data uploads && chown -R appuser:appgroup data uploads

# Switch to non-root user
USER appuser

# Render injects PORT; default to 8080
ENV PORT=8080
EXPOSE 8080

# Health check so Render knows when the app is ready
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/api/health')"

# Start the server — 0.0.0.0 required so Render can route traffic in
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1"]

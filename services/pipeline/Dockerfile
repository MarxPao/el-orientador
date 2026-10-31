FROM python:3.11-slim

# System dependencies for PyMuPDF, fitz, and psycopg
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install python dependencies
COPY services/pipeline/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code and versioned prompts
COPY services/pipeline/app/ ./app/
COPY prompts/ /prompts/

# Create non-root user and persistent storage directory
RUN useradd -m -u 1000 appuser && \
    mkdir -p /app/storage && \
    chown -R appuser:appuser /app

USER appuser

ENV PYTHONPATH=/app
ENV STORAGE_DIR=/app/storage
ENV ENV=production

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]

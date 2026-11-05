FROM python:3.11-slim

# System dependencies for PyMuPDF, fitz, psycopg and OCR (Tesseract, Portuguese + English)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    tesseract-ocr \
    tesseract-ocr-por \
    tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Local embedding model: downloaded once at build time and kept in the image, so semantic search
# works offline afterwards. Must match LOCAL_EMBED_MODEL at runtime (docker-compose passes the same value).
ARG LOCAL_EMBED_MODEL=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
ENV FASTEMBED_CACHE_PATH=/app/models

# Install python dependencies
COPY services/pipeline/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

RUN python -c "from fastembed import TextEmbedding; TextEmbedding(model_name='${LOCAL_EMBED_MODEL}', cache_dir='/app/models')"

# Copy source code and versioned prompts
COPY services/pipeline/app/ ./app/
COPY prompts/ /prompts/
# Migrations applied at startup when AUTO_MIGRATE=1
COPY db/migrations/ /app/migrations/

# Create non-root user and persistent storage directory
RUN useradd -m -u 1000 appuser && \
    mkdir -p /app/storage && \
    chown -R appuser:appuser /app

USER appuser

ENV PYTHONPATH=/app
# OCR for scanned PDFs (PyMuPDF reads the language data from here)
ENV TESSDATA_PREFIX=/usr/share/tesseract-ocr/5/tessdata
ENV STORAGE_DIR=/app/storage
ENV ENV=production

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]

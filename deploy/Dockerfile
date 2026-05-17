FROM python:3.11-slim

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    make \
    && rm -rf /var/lib/apt/lists/*

# Copy project
COPY . .

# Install Python dependencies via pyproject.toml
RUN pip install --no-cache-dir ".[local_llm]"

# Create data directories
RUN mkdir -p data/conversations data/docs data/training/output

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["python", "riycol.py", "run", "server"]

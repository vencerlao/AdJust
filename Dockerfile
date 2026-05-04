FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV HF_HOME=/app/.cache/huggingface

# Copy requirements
COPY backend/requirements_hf.txt requirements.txt

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy models directory first (separate layer for better caching)
COPY backend/models/ /app/models/

# Copy application files
COPY backend/app_hf.py /app/app_hf.py
COPY backend/.env /app/.env 2>/dev/null || true

# Set working directory
WORKDIR /app

# Create cache directory for transformers
RUN mkdir -p /app/.cache/huggingface

# Expose Gradio default port
EXPOSE 7860

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:7860/info || exit 1

# Run the application
CMD ["python", "app_hf.py"]

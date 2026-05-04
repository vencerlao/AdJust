FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1
ENV HF_HOME=/app/.cache/huggingface

COPY backend/requirements_hf.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/models/ /app/models/
COPY backend/app_hf.py /app/app_hf.py

RUN mkdir -p /app/.cache/huggingface

EXPOSE 7860

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:7860/info || exit 1

CMD ["python", "app_hf.py"]
# Factorio LLM Evaluation Container
FROM python:3.11-slim

WORKDIR /app

# Install minimal system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create output directories
RUN mkdir -p /app/checkpoints /app/logs /app/results

# Non-root user for security
RUN useradd -m -s /bin/bash evaluser && \
    chown -R evaluser:evaluser /app
USER evaluser

# Default entrypoint
ENTRYPOINT ["python", "run_llm_eval.py"]
CMD ["--help"]

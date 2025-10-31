FROM python:3.11-slim

# Metadata
LABEL maintainer="Alabia <contato@alabia.com>"
LABEL description="Alabia Conductor - LLM Orchestrator with MCP"

# Workdir
WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY apps/ ./apps/
COPY packages/ ./packages/
COPY docs/ ./docs/

# Create directories
RUN mkdir -p /app/data/chroma_db /app/secrets /app/logs

# Environment
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run
CMD ["uvicorn", "apps.orchestrator.main:app", "--host", "0.0.0.0", "--port", "8000"]

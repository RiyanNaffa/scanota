# app/Dockerfile
FROM python:3.11-slim

# Non-root user
RUN groupadd --gid 1001 appuser \
    && useradd --uid 1001 --gid appuser --shell /bin/bash --create-home appuser

WORKDIR /srv/app

# Install dependencies first (cache layer)
COPY app/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ ./app/

# Storage dir (mounted as volume at runtime)
RUN mkdir -p /srv/storage && chown appuser:appuser /srv/storage

USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

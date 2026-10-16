# dashboard/Dockerfile
FROM python:3.11-slim

RUN groupadd --gid 1001 appuser \
    && useradd --uid 1001 --gid appuser --shell /bin/bash --create-home appuser

# The code imports itself as the `dashboard` package (dashboard.theme, dashboard.api_client),
# so it must live at /app/dashboard with /app on the import path. WORKDIR stays inside it so
# Streamlit finds .streamlit/config.toml and pages/.
ENV PYTHONPATH=/app
WORKDIR /app/dashboard

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . ./

USER appuser

EXPOSE 8501

CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]

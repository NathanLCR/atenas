FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
# Install the package so the `atenas` CLI (e.g. `atenas doctor`, `atenas demo`)
# is on PATH. Dependencies are already installed from requirements.txt.
RUN pip install --no-cache-dir --no-deps . && \
    mkdir -p data logs memory inbox output && \
    useradd --create-home appuser && \
    chown -R appuser:appuser /app
USER appuser
# The slim image ships no HTTP client binary; probe /health with the interpreter. Inside the container the
# probe comes from loopback, so it passes the local-only guard.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import urllib.request as u; u.urlopen('http://127.0.0.1:8000/health', timeout=4)"]
CMD ["uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"]

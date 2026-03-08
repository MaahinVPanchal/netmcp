# Use GCR mirror to avoid Docker Hub 401 (rate limit / auth issues on some build platforms)
FROM mirror.gcr.io/library/python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

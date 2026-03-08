# For mcp-use / manufact.com: build and run NetMCP (Python) from repo root.
# If the platform detects this Dockerfile, it will use it instead of Node + build commands.
FROM python:3.12-slim

WORKDIR /app

COPY netmcp/mcp-server/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY netmcp/mcp-server/ .

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

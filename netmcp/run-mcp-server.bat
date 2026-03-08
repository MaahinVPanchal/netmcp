@echo off
cd /d "%~dp0"

echo Stopping any existing NetMCP server on port 8000...
powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }"
timeout /t 2 /nobreak >nul

cd mcp-server
if not exist .env (
  echo Creating .env from .env.example...
  copy "..\.env.example" .env 2>nul || copy ".env.example" .env 2>nul
)
set STORAGE_BACKEND=file
set NETMCP_LOG_FILE=netmcp_logs.txt

echo.
echo NetMCP server starting. Config loaded from ../mcp.json (frontend_url, backend_url).
echo MCP URL: http://localhost:8000/mcp
echo Press Ctrl+C to stop.
echo.
python main.py

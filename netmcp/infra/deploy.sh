#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

echo "Building NetMCP (SAM)..."
sam build

echo "Deploying (guided on first run)..."
sam deploy --guided

echo "Done. Set MCP_SERVER_URL and MCP_INGEST_URL to the API URL from the stack outputs."

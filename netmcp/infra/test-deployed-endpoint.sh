#!/usr/bin/env bash
# Test NetMCP LIVE (AWS) - run in Git Bash or WSL
# Base URL from stack output: NetMCPApiUrl
BASE="${NETMCP_BASE_URL:-https://r06a66ywad.execute-api.us-east-1.amazonaws.com/Prod}"

echo "=== Testing LIVE NetMCP (AWS) ==="
echo "Base URL: $BASE"
echo ""

echo "1. Health (GET /health)"
curl -s -w "\n   HTTP %{http_code}\n" "$BASE/health"
echo ""

echo "2. Routes (GET /routes) – list deployed endpoints"
curl -s -w "\n   HTTP %{http_code}\n" "$BASE/routes"
echo ""

echo "3. OpenAPI (GET /openapi.json) – paths only"
curl -s "$BASE/openapi.json" | grep -o '"\/[^"]*"' | head -20
echo ""

echo "4. MCP initialize (POST /mcp with Accept header)"
curl -s -w "\n   HTTP %{http_code}\n" -X POST "$BASE/mcp" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"cursor","version":"1.0"}}}'
echo ""
echo "Done."

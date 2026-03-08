#!/usr/bin/env bash
# Run from netmcp/infra: ./invoke-lambda.sh [initialize|tools-list]
set -e
cd "$(dirname "$0")" || true
FUNC=$(aws lambda list-functions --query "Functions[?contains(FunctionName, 'NetMCP')].FunctionName | [0]" --output text --region us-east-1)
if [ -z "$FUNC" ] || [ "$FUNC" = "None" ]; then
  echo "No NetMCP Lambda found. Deploy first."
  exit 1
fi
TEST=${1:-initialize}
if [ "$TEST" = "tools-list" ]; then
  PAYLOAD="$(pwd)/lambda-events/post-mcp-tools-list.json"
else
  PAYLOAD="$(pwd)/lambda-events/post-mcp-initialize.json"
fi
echo "Invoking: $FUNC (test=$TEST)"
aws lambda invoke \
  --function-name "$FUNC" \
  --payload "file://${PAYLOAD}" \
  --region us-east-1 \
  lambda-response.json
echo ""
echo "Response:"
cat lambda-response.json
echo ""

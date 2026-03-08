#!/usr/bin/env bash
# Run from WSL to build and deploy NetMCP to AWS (avoids Windows pywin32 issues).
#
# One-time setup in WSL:
#   1. Install SAM (if not done): see below.
#   2. Configure AWS:  aws configure   (use same Access Key ID & Secret as Windows).
#
# Usage:
#   From PowerShell:  wsl bash /mnt/d/Coding/Hanuman/Awsmcp/netmcp/infra/deploy-wsl.sh
#   From WSL:          cd /mnt/d/Coding/Hanuman/Awsmcp/netmcp/infra && bash deploy-wsl.sh

set -e
INFRA_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$INFRA_DIR"

echo "=== NetMCP build & deploy (WSL) ==="
echo "Infra dir: $INFRA_DIR"

# 1) SAM CLI
if ! command -v sam &>/dev/null; then
  echo "SAM CLI not found. Install once with:"
  echo "  curl -L https://github.com/aws/aws-sam-cli/releases/latest/download/aws-sam-cli-linux-x86_64.zip -o aws-sam-cli.zip"
  echo "  unzip -o aws-sam-cli.zip -d sam-installation"
  echo "  sudo ./sam-installation/install"
  echo "  rm -rf sam-installation aws-sam-cli.zip"
  exit 1
fi
echo "SAM: $(sam --version 2>/dev/null || true)"

# 2) AWS credentials (use same as Windows: run aws configure in WSL once)
if ! aws sts get-caller-identity &>/dev/null; then
  echo "AWS CLI not configured in WSL. Run once:  aws configure"
  echo "Use the same Access Key ID and Secret as in Windows."
  exit 1
fi
echo "AWS identity: $(aws sts get-caller-identity --query Account --output text)"

# 3) Build (Linux build - no pywin32)
echo ""
echo ">>> sam build"
sam build

# 4) Deploy
if [ -f samconfig.toml ]; then
  echo ""
  echo ">>> sam deploy (using saved config)"
  sam deploy
else
  echo ""
  echo ">>> sam deploy --guided (first time)"
  sam deploy --guided
fi

echo ""
echo "=== Done. Get your live URL from the Outputs above (NetMCPApiUrl)."
echo "Cursor MCP URL = that base + /mcp   e.g. https://xxx.execute-api.us-east-1.amazonaws.com/Prod/mcp"
echo ""
echo "If deploy failed with 'Unable to locate credentials': run  aws configure  in WSL (use same keys as Windows)."

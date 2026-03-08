# NetMCP – Deploy to Lambda with Cost Protection

This guide covers deploying NetMCP to AWS Lambda with built-in cost protection (billing alerts, anomaly detection, Lambda limits).

---

## Prerequisites

- AWS CLI configured (`aws configure`)
- AWS SAM CLI installed (`sam --version`)
- IAM permissions (see `iam-policy-netmcp-deploy.json`)

---

## Build (Windows/Linux)

Use Linux wheels so the build doesn't pull platform-specific deps:

**PowerShell:**
```powershell
cd netmcp\infra
$env:PIP_PLATFORM = "manylinux2014_x86_64"
sam build
```

**Bash:**
```bash
cd netmcp/infra
export PIP_PLATFORM=manylinux2014_x86_64
sam build
```

---

## Deploy

### Basic Deploy

```powershell
sam deploy `
  --no-confirm-changeset `
  --parameter-overrides `
    "FrontendUrl=https://your-app.com" `
    "BackendUrl=https://your-project.supabase.co" `
  --capabilities CAPABILITY_IAM
```

### Deploy with Cost Protection (Recommended)

```powershell
sam deploy `
  --no-confirm-changeset `
  --parameter-overrides `
    "FrontendUrl=https://your-app.com" `
    "BackendUrl=https://your-project.supabase.co" `
    "AlertEmail=your-email@example.com" `
    "MonthlyBudget=15" `
  --capabilities CAPABILITY_IAM
```

### Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `FrontendUrl` | Your app's frontend URL | (empty) |
| `BackendUrl` | API/Supabase base URL | (empty) |
| `AlertEmail` | Email for billing alerts | (empty) |
| `MonthlyBudget` | Billing alert threshold in USD | 15 |

---

## Cost Protection Features

The deployment includes these safeguards to keep costs under $20/month:

### 1. Billing Alarm (CloudWatch)
- Triggers when estimated monthly charges exceed threshold (default $15)
- Sends SNS notification to your email

### 2. Cost Anomaly Detection
- Monitors Lambda, DynamoDB, and API Gateway
- Alerts on unusual spending patterns
- Immediate notification

### 3. Lambda Reserved Concurrency
- Max 10 concurrent executions
- Prevents runaway invocations

### 4. DynamoDB TTL
- Data automatically expires after 24 hours
- No manual cleanup needed

### 5. Log Retention
- CloudWatch logs kept for 7 days only
- Automatic cleanup

### 6. Daily Cleanup Job
- Scheduled Lambda removes old records
- Fallback for TTL

---

## Test with PowerShell

After deployment, get the API URL from stack outputs (e.g., `https://xxx.execute-api.us-east-1.amazonaws.com/Prod/`).

```powershell
$BASE = "https://YOUR_API.execute-api.us-east-1.amazonaws.com/Prod"
```

### Health Check
```powershell
Invoke-RestMethod -Uri "$BASE/health" -Method Get
```

### MCP Initialize
```powershell
$body = '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}'
Invoke-RestMethod -Uri "$BASE/mcp-http" -Method Post -Body $body -ContentType "application/json"
```

### List Tools
```powershell
$body = '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
Invoke-RestMethod -Uri "$BASE/mcp-http" -Method Post -Body $body -ContentType "application/json"
```

### fetch_and_extract_apis (Lambda-safe, no browser)
```powershell
$body = '{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tools/call",
  "params": {
    "name": "fetch_and_extract_apis",
    "arguments": {
      "url": "https://your-app.com",
      "fetch_linked_js": true,
      "max_js": 3
    }
  }
}'
(Invoke-RestMethod -Uri "$BASE/mcp-http" -Method Post -Body $body -ContentType "application/json").result.content[0].text | ConvertFrom-Json
```

### get_network_logs
```powershell
$body = '{
  "jsonrpc": "2.0",
  "id": 3,
  "method": "tools/call",
  "params": {
    "name": "get_network_logs",
    "arguments": {
      "limit": 10,
      "include_bodies": false
    }
  }
}'
(Invoke-RestMethod -Uri "$BASE/mcp-http" -Method Post -Body $body -ContentType "application/json").result.content[0].text | ConvertFrom-Json
```

### get_backend_urls
```powershell
$body = '{
  "jsonrpc": "2.0",
  "id": 4,
  "method": "tools/call",
  "params": {
    "name": "get_backend_urls",
    "arguments": {
      "limit": 20
    }
  }
}'
(Invoke-RestMethod -Uri "$BASE/mcp-http" -Method Post -Body $body -ContentType "application/json").result.content[0].text | ConvertFrom-Json
```

### get_failed_requests
```powershell
$body = '{
  "jsonrpc": "2.0",
  "id": 5,
  "method": "tools/call",
  "params": {
    "name": "get_failed_requests",
    "arguments": {
      "limit": 10
    }
  }
}'
(Invoke-RestMethod -Uri "$BASE/mcp-http" -Method Post -Body $body -ContentType "application/json").result.content[0].text | ConvertFrom-Json
```

### search_requests
```powershell
$body = '{
  "jsonrpc": "2.0",
  "id": 6,
  "method": "tools/call",
  "params": {
    "name": "search_requests",
    "arguments": {
      "url_contains": "supabase",
      "limit": 10
    }
  }
}'
(Invoke-RestMethod -Uri "$BASE/mcp-http" -Method Post -Body $body -ContentType "application/json").result.content[0].text | ConvertFrom-Json
```

---

## Test with Bash/curl

```bash
BASE="https://YOUR_API.execute-api.us-east-1.amazonaws.com/Prod"

# Health
curl -s "$BASE/health"

# Initialize
curl -s -X POST "$BASE/mcp-http" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}'

# List tools
curl -s -X POST "$BASE/mcp-http" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' | jq

# fetch_and_extract_apis
curl -s -X POST "$BASE/mcp-http" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/call",
    "params": {
      "name": "fetch_and_extract_apis",
      "arguments": {
        "url": "https://your-app.com"
      }
    }
  }' | jq

# get_network_logs
curl -s -X POST "$BASE/mcp-http" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 3,
    "method": "tools/call",
    "params": {
      "name": "get_network_logs",
      "arguments": {
        "limit": 10
      }
    }
  }' | jq
```

---

## Cursor / Claude Code Configuration

After deployment, add to your MCP config:

```json
{
  "mcpServers": {
    "netmcp": {
      "command": "npx",
      "args": [
        "mcp-remote",
        "https://YOUR_API.execute-api.us-east-1.amazonaws.com/Prod/mcp-http"
      ]
    }
  }
}
```

---

## Monitoring Costs

### View Billing Alarm
```powershell
aws cloudwatch describe-alarms --alarm-names "NetMCP-monthly-budget-alert"
```

### View Cost Anomaly Detector
```powershell
aws ce get-anomaly-monitors
```

### Estimate Costs
```powershell
# Get current month estimate
aws ce get-cost-and-usage `
  --time-period Start=$(Get-Date -Format "yyyy-MM-01"),End=$(Get-Date -Format "yyyy-MM-dd") `
  --granularity MONTHLY `
  --metrics BlendedCost
```

---

## Cleanup / Delete Stack

To remove all resources and stop billing:

```powershell
sam delete --stack-name NetMCP
```

**Note:** This deletes the DynamoDB table and all stored data.

---

## Troubleshooting

### Deployment fails with IAM permissions
Ensure your IAM user/role has the permissions in `iam-policy-netmcp-deploy.json`.

### Lambda timeout
The template sets 30s timeout. For complex pages, this may not be enough. Increase in `template.yaml`:
```yaml
Timeout: 60
```

### High DynamoDB costs
DynamoDB on-demand pricing can spike with heavy scanning. The tools use pagination, but if costs are high:
1. Check CloudWatch metrics for read/write capacity
2. Consider adding Global Secondary Indexes for common queries
3. Adjust scan limits in `db.py`

### Billing alerts not received
- Verify email subscription in SNS console
- Check spam folders
- Ensure `AlertEmail` parameter was set during deploy

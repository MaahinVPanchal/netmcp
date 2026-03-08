# Deploy NetMCP to AWS

Deploy NetMCP so the MCP server and ingest API run on API Gateway + Lambda with DynamoDB storage. Network logs (from browser extension or proxy) are stored in DynamoDB and tools like **get_network_logs**, **get_failed_requests**, **search_requests** work against the live API.

**Note:** Browser automation tools (**navigate_to_app**, **navigate_with_playwright**) do **not** run on Lambda (no Chrome). Use them locally; point Cursor at your deployed URL for log tools only, or run the server locally when you need “open in browser + capture.”

---

## Prerequisites

1. **AWS CLI** installed and configured (`aws configure`).
2. **AWS SAM CLI** installed. **Windows:** see [DEPLOY-AWS-WINDOWS.md](DEPLOY-AWS-WINDOWS.md) (MSI installer, no Docker).
3. **Python 3.11** (for `sam build`).

---

## 1. Config: mcp.json vs .env

- **Local:** Prefer **mcp.json** (section `netmcp`):
  - `frontend_url`, `backend_url`
  - `storage_backend` (`file` or `dynamodb`)
  - `netmcp_log_file` (e.g. `netmcp_logs.txt`) when `storage_backend` is `file`
- **AWS:** Storage is DynamoDB. `FRONTEND_URL` and `BACKEND_URL` are set via SAM **Parameters** (see template) and passed to Lambda env. No mcp.json in the cloud.

So you **manage the two things** (storage backend + log file) in **mcp.json** for local dev; for AWS they are fixed (DynamoDB, no log file).

---

## 2. Deploy steps

From the repo root (or `netmcp` folder):

```bash
cd netmcp/infra
```

**Build:**

```bash
sam build
```

**Deploy (first time – guided):**

```bash
sam deploy --guided
```

- **Stack name:** e.g. `netmcp`
- **AWS Region:** e.g. `us-east-1`
- **Confirm changes:** Y
- **Allow SAM CLI IAM role creation:** Y
- **Disable rollback:** N (recommended)
- **FrontendUrl / BackendUrl:** Accept defaults or set your app URLs
- **Save arguments to config:** Y (so next time you can use `sam deploy` without `--guided`)

**Deploy (later runs):**

```bash
sam build && sam deploy
```

---

## 3. After deploy

1. **Get the API URL** from outputs:
   ```bash
   aws cloudformation describe-stacks --stack-name netmcp --query "Stacks[0].Outputs[?OutputKey=='NetMCPApiUrl'].OutputValue" --output text
   ```
   Or in AWS Console: **CloudFormation → Stacks → netmcp → Outputs → NetMCPApiUrl**.

2. **Point Cursor at the live MCP:**
   - In **mcp.json** (e.g. `~/.cursor/mcp.json` or project `netmcp/mcp.json`), set:
     ```json
     "netmcp": {
       "url": "https://xxxxxxxxxx.execute-api.us-east-1.amazonaws.com/Prod/mcp"
     }
     ```
   - Use the full MCP path: `/Prod/mcp` (the server mounts the MCP app at `/mcp`).

3. **Ingest URL for extension/proxy:**  
   `https://<same-api-id>.execute-api.<region>.amazonaws.com/Prod/ingest`  
   Configure your browser extension or proxy to send logs to this URL.

---

## 4. What runs where

| Feature              | Local server        | AWS (Lambda)     |
|----------------------|--------------------|------------------|
| Ingest (store logs) | ✅                  | ✅               |
| get_network_logs     | ✅                  | ✅               |
| get_failed_requests  | ✅                  | ✅               |
| search_requests      | ✅                  | ✅               |
| navigate_to_app      | ✅ (opens browser) | ❌ (no Chrome)   |

Use **local** NetMCP when you want “open project in browser + capture”; use **deployed** NetMCP for shared log storage and tools from Cursor/other clients.

---

## 5. Login / Signup automation (future)

You asked: *“It should understand through live frontend content, taking image or screenshot, so when user says login or signup it clicks the right button.”*

**Idea:** Add a tool that:

1. Uses Playwright to open the frontend (as now).
2. Takes a **screenshot** of the current page.
3. Sends the screenshot to a **vision model** (e.g. GPT-4V or Claude) with the user intent: “Find and click the Login button” or “Find and click Sign Up.”
4. The model returns the **selector or coordinates** of the button.
5. Playwright **clicks** that element and optionally continues (e.g. fill form, capture network).

This would run **only locally** (or on an ECS/EC2 with a browser), not on Lambda. We can add this as a follow-up once the current deploy and config are in place.

---

## 6. Test via direct Lambda invoke (AWS CLI)

If the API Gateway URL returns quickly but **tools don’t load** or `/mcp` doesn’t behave as expected, invoke the Lambda directly to see the real response and any errors (no API Gateway in the path).

**Option A – PowerShell script (Windows):**

```powershell
cd netmcp/infra
.\invoke-lambda.ps1                    # auto-detects function, runs MCP initialize
.\invoke-lambda.ps1 -Test tools-list   # list tools
.\invoke-lambda.ps1 -Test health       # GET /health
.\invoke-lambda.ps1 -FunctionName netmcp-NetMCPFunction-XXXXXXXXX  # explicit name
```

**Option B – Raw AWS CLI:**

Get the function name (after deploy):

```bash
aws lambda list-functions --query "Functions[?contains(FunctionName, 'NetMCP')].FunctionName" --output text
```

Invoke with an API Gateway–shaped event (path `/mcp`, POST body = MCP initialize):

```bash
cd netmcp/infra
aws lambda invoke \
  --function-name YOUR-NetMCP-Function-Name \
  --payload file://lambda-events/post-mcp-initialize.json \
  --cli-binary-format raw-in-base64-out \
  lambda-response.json
type lambda-response.json   # Windows
# cat lambda-response.json  # Linux/Mac
```

Check `lambda-response.json`: it should contain `statusCode: 200` and a `body` with `serverInfo` (MCP initialize). If you see 404 or empty body, the path or Mangum routing may be wrong; check CloudWatch logs for the same request.

To test tools list:

```bash
aws lambda invoke \
  --function-name YOUR-NetMCP-Function-Name \
  --payload file://lambda-events/post-mcp-tools-list.json \
  --cli-binary-format raw-in-base64-out \
  lambda-response.json
```

---

## 7. Troubleshooting

- **502/503:** Check Lambda logs in CloudWatch (Log group: `/aws/lambda/<stack-name>-NetMCPFunction-...`). Common: timeout (increase in template), missing env, or DynamoDB permissions (template grants Crud policy).
- **/mcp returns 200 but tools don’t load:** Use **direct Lambda invoke** (Section 6) and inspect the response body and CloudWatch logs; often the request is hitting the wrong path or the MCP JSON-RPC response is not what the client expects.
- **CORS:** Template uses Mangum; API Gateway may need CORS headers if you call from a browser. Add if needed.
- **MCP connection:** Ensure the URL in mcp.json is the **Prod** stage base URL and that Cursor can reach it (no VPN/firewall blocking).

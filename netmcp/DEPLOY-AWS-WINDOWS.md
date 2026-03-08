# Deploy NetMCP to AWS on Windows (no Docker)

Get a **live URL** for your NetMCP MCP server on AWS. Uses **AWS SAM CLI** (no Docker needed for this app).

**If `sam build` fails on Windows** (e.g. pywin32 or Python version errors), use **WSL** – see [Option B: Build & deploy from WSL](#option-b-build--deploy-from-wsl-recommended-if-windows-build-fails) below.

---

## Option B: Build & deploy from WSL (recommended if Windows build fails)

If `sam build` on Windows fails (e.g. **pywin32** or **Python version**), use WSL. The build already succeeded in WSL; you only need to configure AWS in WSL once and deploy.

**1. Open WSL** (e.g. `wsl` in PowerShell or Ubuntu from Start).

**2. Configure AWS in WSL (one time)** – use the same Access Key ID and Secret as in Windows:
```bash
aws configure
```

**3. Deploy** (from WSL):
```bash
cd /mnt/d/Coding/Hanuman/Awsmcp/netmcp/infra
bash deploy-wsl.sh
```
Or from PowerShell:  
`wsl bash /mnt/d/Coding/Hanuman/Awsmcp/netmcp/infra/deploy-wsl.sh`

- If this is the first deploy, `sam deploy --guided` will run; use stack name `netmcp`, region `us-east-1`, and accept the rest (or press Enter for defaults).
- At the end you’ll see **Outputs** with **NetMCPApiUrl** – that’s your live base URL. Cursor MCP URL = base + `/mcp`.

**Note:** SAM CLI was already installed in WSL for you. The template uses **Python 3.10** so it matches WSL’s default `python3`.

---

## Step 1: Install AWS SAM CLI on Windows (Option A)

You already have **AWS CLI** and `aws configure` set up. Add SAM CLI:

1. **Download the SAM CLI installer (64-bit):**  
   https://github.com/aws/aws-sam-cli/releases/latest/download/AWS_SAM_CLI_64_PY3.msi

2. **Run the MSI** and complete the installer (next → next).

3. **Open a new PowerShell window** (so `PATH` is updated) and check:
   ```powershell
   sam --version
   ```
   You should see something like `SAM CLI, 1.xxx.x`.

---

## Step 2: Deploy to AWS

In PowerShell:

```powershell
cd D:\Coding\Hanuman\Awsmcp\netmcp\infra
sam build
sam deploy --guided
```

**First-time `sam deploy --guided` – use these:**

| Prompt | What to enter |
|--------|-------------------------------|
| Stack Name | `netmcp` (or any name) |
| AWS Region | `us-east-1` (or your region) |
| Parameter FrontendUrl | Your frontend URL (e.g. https://your-app.com) |
| Parameter BackendUrl | Your backend/API URL (e.g. Supabase project URL) |
| Confirm changes before deploy | `y` |
| Allow SAM CLI IAM role creation | `y` |
| Disable rollback | `n` |
| Save arguments to configuration file | `y` |
| SAM configuration file | Enter (default) |
| SAM configuration environment | Enter (default) |

Deploy takes a few minutes. At the end you’ll see **Outputs** including the live URL.

---

## Step 3: Get your live URL

After deploy, the **live base URL** is in CloudFormation:

**Option A – PowerShell:**
```powershell
aws cloudformation describe-stacks --stack-name netmcp --query "Stacks[0].Outputs[?OutputKey=='NetMCPApiUrl'].OutputValue" --output text
```

**Option B – AWS Console:**  
CloudFormation → Stacks → **netmcp** → **Outputs** → **NetMCPApiUrl**.

Example value:
`https://abc123xyz.execute-api.us-east-1.amazonaws.com/Prod/`

Your **MCP endpoint** (for Cursor) is that URL + `mcp`:

```
https://abc123xyz.execute-api.us-east-1.amazonaws.com/Prod/mcp
```

---

## Step 4: Point Cursor at the live MCP

Edit your MCP config (e.g. `C:\Users\Owner\.cursor\mcp.json`) and set the **netmcp** URL to the live MCP endpoint:

```json
"netmcp": {
  "url": "https://YOUR-API-ID.execute-api.us-east-1.amazonaws.com/Prod/mcp"
}
```

Replace `YOUR-API-ID` and region with the value from Step 3. Restart Cursor or reload MCP so it uses the new URL.

---

## Step 5: Ingest URL (browser extension / proxy)

To send network logs to the same stack, use:

```
https://YOUR-API-ID.execute-api.us-east-1.amazonaws.com/Prod/ingest
```

Configure your NetMCP browser extension or proxy with this URL so logs are stored in DynamoDB and show up in **get_network_logs** / **get_failed_requests** when using the live MCP URL in Cursor.

---

## Summary

| What | Where |
|------|--------|
| Install SAM | MSI from GitHub (link in Step 1) |
| Build & deploy | `sam build` then `sam deploy --guided` in `netmcp/infra` |
| Live base URL | CloudFormation output **NetMCPApiUrl** |
| Cursor MCP URL | Base URL + `mcp` (e.g. `.../Prod/mcp`) |
| Ingest URL | Base URL + `ingest` (e.g. `.../Prod/ingest`) |

No Docker is required; the Lambda uses a small dependency set (see `mcp-server/requirements.txt`). For local dev with browser tools, use `pip install -r requirements-dev.txt`.

---

## If `sam build` fails

- **“sam is not recognized”** – Close and reopen PowerShell after installing SAM; or add the SAM install folder to your PATH.
- **“PythonPipBuilder:ResolveDependencies - pywin32”** – Use **Option B (WSL)** above; build and deploy from WSL to avoid Windows-only packages.
- **“Binary validation failed for python... runtime: python3.10”** – The template uses **Python 3.10** for WSL. If you build on Windows, set `Runtime:` in `infra/template.yaml` to match your `python --version` (e.g. `python3.12`), or use **Option B (WSL)**.
- **Long path errors** – Enable long paths: [Windows docs](https://learn.microsoft.com/en-us/windows/win32/fileio/maximum-file-path-limitation#enable-long-paths-in-windows-10-version-1607-and-later).
- **AWS credentials** – Run `aws configure` and use an IAM user/role that can create CloudFormation stacks, Lambda, API Gateway, and DynamoDB. Your account ID (e.g. 717279715087) is used automatically when you’re logged in.

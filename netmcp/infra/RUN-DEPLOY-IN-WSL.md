# Run SAM build + deploy in your WSL terminal

Do this **in the same WSL terminal** where you ran `wsl` (so `aws` is on PATH).

## 1. Create the S3 bucket once (if not exists)

In WSL (user must have `s3:CreateBucket` permission):

```bash
aws s3 mb s3://netmcp-sam-artifacts --region us-east-1
```

If you get **AccessDenied**, your IAM user needs more permissions. See **[IAM-SETUP.md](IAM-SETUP.md)** in this folder: use root or an admin to run `setup-iam-for-deploy.sh`, or create the bucket in the AWS Console as root and attach the policy from `iam-policy-netmcp-deploy.json` to your user.

## 2. Build and deploy

In WSL (from any directory, or from project root):

```bash
cd /mnt/d/Coding/Hanuman/Awsmcp/netmcp/infra
sam build
sam deploy --parameter-overrides "FrontendUrl=https://your-frontend-url.com" "BackendUrl=https://your-backend-url.com"
```

Replace `your-frontend-url.com` and `your-backend-url.com` with your actual app URL and API URL (e.g. Supabase project URL). When it asks **Confirm changes before deploy** [y/N], type `y` and Enter.

**Same two URLs when connecting:** In `mcp.json` (Cursor or extension), set `netmcp.frontend_url` and `netmcp.backend_url` to the same values so the MCP client uses your app and backend.

## 3. If you get "User ... is not authorized to perform: cloudformation:CreateChangeSet"

That was for SAM’s **managed** bucket. Using the bucket above avoids it. If you still see CloudFormation errors for the **netmcp** stack, your IAM user needs something like:

- `cloudformation:CreateStack`, `cloudformation:UpdateStack`, `cloudformation:CreateChangeSet`, `cloudformation:Describe*`, `cloudformation:ExecuteChangeSet`
- Plus Lambda, API Gateway, DynamoDB, S3, IAM (pass role) as in the template.

Or use a user/role with **AdministratorAccess** for the first deploy.

## 4. Get your live URL

After a successful deploy, the output shows **NetMCPApiUrl**. Your Cursor MCP URL is that value + `/mcp`, e.g.:

`https://xxxxxxxxxx.execute-api.us-east-1.amazonaws.com/Prod/mcp`

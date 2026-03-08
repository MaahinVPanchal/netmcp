# Fix “AccessDenied” for S3 / SAM deploy (IAM user AwsAiHack)

Your IAM user `AwsAiHack` needs extra permissions to create the S3 bucket and run SAM deploy. Use **one** of the options below.

---

## Option 1: CLI as root or admin (recommended)

Use credentials that can manage IAM (root or an admin user), then run:

```bash
cd /mnt/d/Coding/Hanuman/Awsmcp/netmcp/infra
chmod +x setup-iam-for-deploy.sh
bash setup-iam-for-deploy.sh
```

**If you only have AwsAiHack:** sign in to the **AWS Console as root** → IAM → Users → create an admin user (or use root) → Security credentials → Create access key → use that key with `aws configure` in WSL, then run the script above.

After the script succeeds, **switch back to AwsAiHack** (or keep using the same terminal if it’s already AwsAiHack) and run:

```bash
aws s3 mb s3://netmcp-sam-artifacts --region us-east-1
cd /mnt/d/Coding/Hanuman/Awsmcp/netmcp/infra
sam build
sam deploy --parameter-overrides "FrontendUrl=https://your-frontend-url.com" "BackendUrl=https://your-backend-url.com"
```

---

## Option 2: Console – create bucket as root, then attach policy to AwsAiHack

1. **Create the bucket (as root or any user that has S3 create):**  
   AWS Console → S3 → Create bucket → name: `netmcp-sam-artifacts` → Create.

2. **Grant AwsAiHack permissions:**  
   IAM → Users → **AwsAiHack** → Add permissions → Create inline policy → JSON tab → paste the contents of `infra/iam-policy-netmcp-deploy.json` → Next → name e.g. `NetmcpSamDeploy` → Create policy.

Then in WSL as AwsAiHack:

```bash
cd /mnt/d/Coding/Hanuman/Awsmcp/netmcp/infra
sam build
sam deploy --parameter-overrides "FrontendUrl=https://your-frontend-url.com" "BackendUrl=https://your-backend-url.com"
```

---

## What the policy allows

The policy in `iam-policy-netmcp-deploy.json` allows:

- **S3:** create and use bucket `netmcp-sam-artifacts` (SAM artifacts).
- **CloudFormation:** create/update/delete stacks (e.g. netmcp).
- **Lambda:** create/update/delete functions.
- **API Gateway:** create and manage the REST API.
- **DynamoDB:** create and use the NetMCP table.
- **IAM:** create/attach roles and policies needed for the Lambda execution role.
- **CloudWatch Logs:** create log groups for Lambda.

No account ID or other secrets are in the policy; it’s scoped to these actions and the artifact bucket name.

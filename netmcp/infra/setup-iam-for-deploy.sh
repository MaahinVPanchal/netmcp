#!/usr/bin/env bash
# Grant IAM user AwsAiHack permission to create S3 bucket + full SAM deploy (NetMCP).
#
# WHO CAN RUN THIS:
#   You must be signed in as AWS root OR an IAM user/role that can create policies
#   and attach them to users (e.g. AdministratorAccess). The user "AwsAiHack" cannot
#   grant themselves; use root or another admin.
#
# OPTION A - Using root or admin credentials in CLI:
#   1. aws configure   (use root or admin access key)
#   2. bash setup-iam-for-deploy.sh
#
# OPTION B - Using root in browser, then create admin key:
#   1. Sign in to AWS Console as root
#   2. IAM -> Users -> Create user "admin-deploy" (or use existing admin)
#   3. Attach policy "AdministratorAccess", create Access Key, run aws configure with that key
#   4. bash setup-iam-for-deploy.sh
#
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
POLICY_FILE="$SCRIPT_DIR/iam-policy-netmcp-deploy.json"
USER_NAME="AwsAiHack"
POLICY_NAME="NetmcpSamDeployPolicy"

echo "Creating IAM policy: $POLICY_NAME"
aws iam create-policy --policy-name "$POLICY_NAME" --policy-document "file://$POLICY_FILE" --description "Allow SAM deploy for NetMCP" 2>/dev/null || true

ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
POLICY_ARN="arn:aws:iam::${ACCOUNT_ID}:policy/${POLICY_NAME}"

echo "Attaching policy to user: $USER_NAME"
aws iam attach-user-policy --user-name "$USER_NAME" --policy-arn "$POLICY_ARN"

echo "Done. User $USER_NAME can now create bucket and run sam deploy."

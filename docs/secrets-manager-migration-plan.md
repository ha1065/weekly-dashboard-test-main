# Secrets Manager Migration Plan

Move two Lambda API keys from plaintext environment variables into AWS Secrets Manager.
No key rotation — values are migrated as-is.

**Account:** 961341524729 | **Region:** us-east-1

---

## 1. Current State

### Secrets Manager — existing secrets

One relevant secret already exists:

| Secret Name | ARN |
|---|---|
| `production/weekly-reporting/secrets` | `arn:aws:secretsmanager:us-east-1:961341524729:secret:production/weekly-reporting/secrets-wz2cJg` |

This secret is managed by the CloudFormation stack `weekly-reporting-production` and currently holds `clockify_api_key`, `clockify_workspace_id`, and `db_password`. The `clockify-data-processor` Lambda does **not** read from it — it uses a plaintext env var instead.

There is **no existing secret** for the Jira API token.

### Lambda 1 — `jira-data-pull-lambda`

| Item | Value |
|---|---|
| Role | `arn:aws:iam::961341524729:role/service-role/jira-data-pull-lambda-role-qvlxgrdj` |
| Plaintext env var | `JIRA_API_TOKEN` |
| Other env vars to preserve | `S3_BUCKET`, `JIRA_EMAIL`, `JIRA_DOMAIN` |

**Source files that read `JIRA_API_TOKEN`:**

- `src/integrations/jira_client.py` — reads `settings.jira_api_token` (via `src/database/config.py` settings object, which reads `JIRA_API_TOKEN` from env)
- `src/lambda_handler.py` — calls `set_environment_from_secrets()` which sets `os.environ['JIRA_API_TOKEN']` from the `production/weekly-reporting/secrets` secret (this Lambda already has Secrets Manager wiring for the *main* Lambda, but `jira-data-pull-lambda` is a separate, older Lambda that does not)

### Lambda 2 — `clockify-data-processor`

| Item | Value |
|---|---|
| Role | `arn:aws:iam::961341524729:role/Clockify-Quicksight-ClockifyLambdaRole-IwgI7jSFOoyl` |
| Plaintext env var | `CLOCKIFY_API_KEY` |
| Other env vars to preserve | `S3_BUCKET`, `SNS_TOPIC_ARN`, `CLOCKIFY_WORKSPACE_ID`, `QUICKSIGHT_ACCOUNT_ID` |

**Source files that read `CLOCKIFY_API_KEY`:**

- `src/integrations/clockify_client.py` — `ClockifyClient.__init__` reads `settings.clockify_api_key`
- `src/integrations/update_clockify.py` — `_headers()` reads `settings.clockify_api_key`

The `settings` object in `src/database/config.py` reads these values from environment variables. The migration adds a Secrets Manager fetch that populates the env vars before the settings object is used.

---

## 2. AWS CLI Commands

### Step 2a — Create the Jira secret

The Clockify secret already exists (`production/weekly-reporting/secrets`). Only the Jira secret needs to be created.

```bash
aws secretsmanager create-secret \
  --name "production/weekly-reporting/jira" \
  --description "Jira API token for jira-data-pull-lambda" \
  --secret-string '{"jira_api_token":"<JIRA_API_TOKEN_VALUE>"}' \
  --tags '[{"Key":"Environment","Value":"production"},{"Key":"ManagedBy","Value":"manual"}]' \
  --profile AWSAdministratorAccess-961341524729 \
  --region us-east-1
```

> **Note:** Replace `<JIRA_API_TOKEN_VALUE>` with the actual token value from the current `JIRA_API_TOKEN` env var on `jira-data-pull-lambda` before running.

### Step 2b — Grant `jira-data-pull-lambda` access to its secret

```bash
aws iam put-role-policy \
  --role-name jira-data-pull-lambda-role-qvlxgrdj \
  --policy-name SecretsManagerJiraAccess \
  --policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Action": "secretsmanager:GetSecretValue",
      "Resource": "arn:aws:secretsmanager:us-east-1:961341524729:secret:production/weekly-reporting/jira-*"
    }]
  }' \
  --profile AWSAdministratorAccess-961341524729 \
  --region us-east-1
```

### Step 2c — Grant `clockify-data-processor` access to the existing secret

The `clockify_api_key` is already in `production/weekly-reporting/secrets`. The Lambda role just needs permission to read it.

```bash
aws iam put-role-policy \
  --role-name Clockify-Quicksight-ClockifyLambdaRole-IwgI7jSFOoyl \
  --policy-name SecretsManagerClockifyAccess \
  --policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Action": "secretsmanager:GetSecretValue",
      "Resource": "arn:aws:secretsmanager:us-east-1:961341524729:secret:production/weekly-reporting/secrets-*"
    }]
  }' \
  --profile AWSAdministratorAccess-961341524729 \
  --region us-east-1
```

### Step 2d — Add the secret ARN env vars to each Lambda (before removing plaintext vars)

Add `SECRET_NAME` to `jira-data-pull-lambda` (preserving all existing env vars):

```bash
aws lambda update-function-configuration \
  --function-name jira-data-pull-lambda \
  --environment 'Variables={
    "S3_BUCKET":"jira-data-pull-cloudelligent",
    "JIRA_EMAIL":"muhammad.kashif@cloudelligent.com",
    "JIRA_DOMAIN":"https://cloudelligent.atlassian.net",
    "JIRA_API_TOKEN":"<JIRA_API_TOKEN_VALUE>",
    "SECRET_NAME":"production/weekly-reporting/jira"
  }' \
  --profile AWSAdministratorAccess-961341524729 \
  --region us-east-1
```

Add `SECRET_NAME` to `clockify-data-processor` (preserving all existing env vars):

```bash
aws lambda update-function-configuration \
  --function-name clockify-data-processor \
  --environment 'Variables={
    "S3_BUCKET":"clockify-dashboard-961341524729-us-east-1",
    "SNS_TOPIC_ARN":"arn:aws:sns:us-east-1:961341524729:clockify-dashboard-notifications",
    "CLOCKIFY_WORKSPACE_ID":"5dd33a164809562a2449ca65",
    "QUICKSIGHT_ACCOUNT_ID":"961341524729",
    "CLOCKIFY_API_KEY":"<CLOCKIFY_API_KEY_VALUE>",
    "SECRET_NAME":"production/weekly-reporting/secrets"
  }' \
  --profile AWSAdministratorAccess-961341524729 \
  --region us-east-1
```

> Keep the plaintext vars in place during this step. Remove them only after verifying the code changes work (see Step 5).

### Step 2e — Remove plaintext env vars (run AFTER verification)

Remove `JIRA_API_TOKEN` from `jira-data-pull-lambda`:

```bash
aws lambda update-function-configuration \
  --function-name jira-data-pull-lambda \
  --environment 'Variables={
    "S3_BUCKET":"jira-data-pull-cloudelligent",
    "JIRA_EMAIL":"muhammad.kashif@cloudelligent.com",
    "JIRA_DOMAIN":"https://cloudelligent.atlassian.net",
    "SECRET_NAME":"production/weekly-reporting/jira"
  }' \
  --profile AWSAdministratorAccess-961341524729 \
  --region us-east-1
```

Remove `CLOCKIFY_API_KEY` from `clockify-data-processor`:

```bash
aws lambda update-function-configuration \
  --function-name clockify-data-processor \
  --environment 'Variables={
    "S3_BUCKET":"clockify-dashboard-961341524729-us-east-1",
    "SNS_TOPIC_ARN":"arn:aws:sns:us-east-1:961341524729:clockify-dashboard-notifications",
    "CLOCKIFY_WORKSPACE_ID":"5dd33a164809562a2449ca65",
    "QUICKSIGHT_ACCOUNT_ID":"961341524729",
    "SECRET_NAME":"production/weekly-reporting/secrets"
  }' \
  --profile AWSAdministratorAccess-961341524729 \
  --region us-east-1
```

---

## 3. Code Changes

Both Lambdas need a shared helper that fetches the secret and populates env vars before the `settings` object (in `src/database/config.py`) is accessed.

### 3a — Add shared secret loader: `src/utils/secrets.py` (new file)

```python
import json
import os
import boto3

_cache: dict | None = None


def load_secrets() -> None:
    """Fetch secret from Secrets Manager and set env vars. Cached per Lambda container."""
    global _cache
    if _cache is not None:
        return

    secret_name = os.environ.get("SECRET_NAME")
    if not secret_name:
        return  # running locally without Secrets Manager

    client = boto3.client("secretsmanager", region_name=os.environ.get("AWS_REGION", "us-east-1"))
    response = client.get_secret_value(SecretId=secret_name)
    _cache = json.loads(response["SecretString"])

    # Populate env vars so settings object picks them up unchanged
    for key, env_var in (
        ("jira_api_token",       "JIRA_API_TOKEN"),
        ("clockify_api_key",     "CLOCKIFY_API_KEY"),
        ("clockify_workspace_id","CLOCKIFY_WORKSPACE_ID"),
    ):
        if key in _cache and not os.environ.get(env_var):
            os.environ[env_var] = _cache[key]
```

Key design decisions:
- `_cache` is module-level — fetched once per Lambda container lifetime, not per invocation.
- Only sets an env var if it is not already present, so local development (with env vars set directly) continues to work without change.
- No new dependencies — uses `boto3` which is already available in Lambda.

### 3b — `jira-data-pull-lambda` handler (wherever its entry point is)

The `jira-data-pull-lambda` handler file is `lambda_function.lambda_handler` (per the Lambda config). That file is not in this repo — it lives in the deployed zip. The change needed is to call `load_secrets()` at the top of the handler, before any import of `JiraClient` or `settings`.

**Diff to apply to the Lambda's `lambda_function.py`:**

```diff
+from src.utils.secrets import load_secrets
+load_secrets()   # must run before settings is imported

 from src.integrations.jira_client import JiraClient
 # ... rest of imports
```

If the handler directly reads `os.environ["JIRA_API_TOKEN"]` rather than going through `settings`, replace that read:

```diff
-api_token = os.environ["JIRA_API_TOKEN"]
+from src.utils.secrets import load_secrets
+load_secrets()
+api_token = os.environ["JIRA_API_TOKEN"]  # now populated from Secrets Manager
```

### 3c — `clockify-data-processor` handler (`index.lambda_handler`)

The `clockify-data-processor` handler is `index.lambda_handler`. Apply the same pattern:

```diff
+from src.utils.secrets import load_secrets
+load_secrets()   # must run before settings/ClockifyClient is imported

 from src.integrations.clockify_client import ClockifyClient
 # ... rest of imports
```

### 3d — No changes needed to `clockify_client.py` or `update_clockify.py`

Both files read `settings.clockify_api_key`. As long as `load_secrets()` runs before the `settings` object is first accessed, they continue to work without modification. The `settings` object reads from env vars at import time, so `load_secrets()` must be called before the first `import` of any module that touches `settings`.

### 3e — `src/lambda_handler.py` (the main weekly-reporting Lambda)

This Lambda already has its own `get_secrets()` / `set_environment_from_secrets()` pattern and reads from `production/weekly-reporting/secrets`. **No change needed** — it already handles Clockify and Jira credentials correctly via Secrets Manager.

---

## 4. CloudFormation Updates

The `cloudformation/template.yaml` currently manages the `production/weekly-reporting/secrets` secret (resource `ApplicationSecrets`) which holds `clockify_api_key`. The two Lambdas being migrated (`jira-data-pull-lambda` and `clockify-data-processor`) are **not** defined in this template — they are standalone Lambdas managed outside CloudFormation.

Changes to make in `cloudformation/template.yaml`:

### 4a — Add the Jira secret resource

```yaml
  JiraSecrets:
    Type: AWS::SecretsManager::Secret
    Properties:
      Name: !Sub ${Environment}/weekly-reporting/jira
      Description: Jira API token for jira-data-pull-lambda
      SecretString: !Sub |
        {
          "jira_api_token": "${JiraAPIToken}"
        }
      Tags:
        - Key: Environment
          Value: !Ref Environment
```

Add the corresponding parameter:

```yaml
  JiraAPIToken:
    Type: String
    NoEcho: true
    Description: Jira API token for jira-data-pull-lambda
    MinLength: 10
```

### 4b — Remove `ClockifyAPIKey` from `ApplicationSecrets` `SecretString` (optional, long-term)

The `clockify_api_key` is already in `ApplicationSecrets`. No structural change is needed for the Clockify migration — the secret already exists. If you want to stop passing `ClockifyAPIKey` as a CloudFormation parameter in the future (after the old Lambda is fully decommissioned), remove it from the `SecretString` and the `Parameters` block.

### 4c — The `ImportLambdaFunction` in the template already has the correct pattern

The `ImportLambdaFunction` resource uses `SECRET_NAME: !Ref ApplicationSecrets` and the `LambdaExecutionRole` already has `secretsmanager:GetSecretValue` scoped to `!Ref ApplicationSecrets`. This is the correct pattern — the two standalone Lambdas should mirror it once migrated.

---

## 5. Verification Steps

Run these after deploying the code changes but **before** removing the plaintext env vars (so you can roll back easily).

### 5a — Verify IAM permissions

```bash
# Confirm jira-data-pull-lambda role has the new policy
aws iam get-role-policy \
  --role-name jira-data-pull-lambda-role-qvlxgrdj \
  --policy-name SecretsManagerJiraAccess \
  --profile AWSAdministratorAccess-961341524729 \
  --region us-east-1

# Confirm clockify-data-processor role has the new policy
aws iam get-role-policy \
  --role-name Clockify-Quicksight-ClockifyLambdaRole-IwgI7jSFOoyl \
  --policy-name SecretsManagerClockifyAccess \
  --profile AWSAdministratorAccess-961341524729 \
  --region us-east-1
```

### 5b — Verify the Jira secret is readable

```bash
aws secretsmanager get-secret-value \
  --secret-id production/weekly-reporting/jira \
  --query SecretString \
  --output text \
  --profile AWSAdministratorAccess-961341524729 \
  --region us-east-1
```

Confirm the JSON contains `jira_api_token` with a non-empty value.

### 5c — Invoke `jira-data-pull-lambda` with a dry-run or minimal payload

```bash
aws lambda invoke \
  --function-name jira-data-pull-lambda \
  --payload '{}' \
  --log-type Tail \
  --query 'LogResult' \
  --output text \
  --profile AWSAdministratorAccess-961341524729 \
  --region us-east-1 \
  /tmp/jira-response.json | base64 --decode

cat /tmp/jira-response.json
```

Look for a successful response (no `JIRA_API_TOKEN` missing errors). Check CloudWatch logs at `/aws/lambda/jira-data-pull-lambda` for any auth failures.

### 5d — Invoke `clockify-data-processor` with a minimal payload

```bash
aws lambda invoke \
  --function-name clockify-data-processor \
  --payload '{}' \
  --log-type Tail \
  --query 'LogResult' \
  --output text \
  --profile AWSAdministratorAccess-961341524729 \
  --region us-east-1 \
  /tmp/clockify-response.json | base64 --decode

cat /tmp/clockify-response.json
```

Confirm no `401 Unauthorized` or `X-Api-Key` errors from the Clockify API.

### 5e — Confirm the plaintext vars are gone (after Step 2e)

```bash
aws lambda get-function-configuration \
  --function-name jira-data-pull-lambda \
  --query 'Environment.Variables' \
  --profile AWSAdministratorAccess-961341524729 \
  --region us-east-1

aws lambda get-function-configuration \
  --function-name clockify-data-processor \
  --query 'Environment.Variables' \
  --profile AWSAdministratorAccess-961341524729 \
  --region us-east-1
```

Neither response should contain `JIRA_API_TOKEN` or `CLOCKIFY_API_KEY`.

---

## 6. Rollback Plan

If something breaks after the code is deployed but before the plaintext vars are removed, no action is needed — the plaintext vars are still present and the code falls back to them (because `load_secrets()` only sets an env var if it is not already set).

If something breaks **after** the plaintext vars are removed (Step 2e):

### Restore plaintext env vars immediately

```bash
# Restore JIRA_API_TOKEN
aws lambda update-function-configuration \
  --function-name jira-data-pull-lambda \
  --environment 'Variables={
    "S3_BUCKET":"jira-data-pull-cloudelligent",
    "JIRA_EMAIL":"muhammad.kashif@cloudelligent.com",
    "JIRA_DOMAIN":"https://cloudelligent.atlassian.net",
    "JIRA_API_TOKEN":"<JIRA_API_TOKEN_VALUE>",
    "SECRET_NAME":"production/weekly-reporting/jira"
  }' \
  --profile AWSAdministratorAccess-961341524729 \
  --region us-east-1

# Restore CLOCKIFY_API_KEY
aws lambda update-function-configuration \
  --function-name clockify-data-processor \
  --environment 'Variables={
    "S3_BUCKET":"clockify-dashboard-961341524729-us-east-1",
    "SNS_TOPIC_ARN":"arn:aws:sns:us-east-1:961341524729:clockify-dashboard-notifications",
    "CLOCKIFY_WORKSPACE_ID":"5dd33a164809562a2449ca65",
    "QUICKSIGHT_ACCOUNT_ID":"961341524729",
    "CLOCKIFY_API_KEY":"<CLOCKIFY_API_KEY_VALUE>",
    "SECRET_NAME":"production/weekly-reporting/secrets"
  }' \
  --profile AWSAdministratorAccess-961341524729 \
  --region us-east-1
```

Both Lambdas will immediately resume using the plaintext values. The `load_secrets()` helper will skip setting the env var because it is already present.

### Common failure causes and fixes

| Symptom | Likely cause | Fix |
|---|---|---|
| `AccessDeniedException` in Lambda logs | IAM policy not attached or wrong ARN | Re-run Step 2b or 2c |
| `ResourceNotFoundException` | Secret name typo or wrong region | Verify secret name with `list-secrets` |
| `JIRA_API_TOKEN` / `CLOCKIFY_API_KEY` still empty after `load_secrets()` | Secret JSON key name mismatch | Check secret value keys match `jira_api_token` / `clockify_api_key` |
| 401 from Clockify API | Wrong key value stored in secret | Update secret value: `aws secretsmanager put-secret-value --secret-id production/weekly-reporting/secrets --secret-string '{"clockify_api_key":"<value>","clockify_workspace_id":"...","db_password":"..."}'` |

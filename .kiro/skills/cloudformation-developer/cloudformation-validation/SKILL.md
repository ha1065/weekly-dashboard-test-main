---
name: cloudformation-validation
description: CloudFormation/SAM template validation and testing patterns. Use when validating, testing, or deploying CloudFormation templates.
metadata:
  version: '1.0'
---

## Template Validation with cfn-lint

Reference: cfn-lint GitHub (https://github.com/aws-cloudformation/cfn-lint)

Run `cfn-lint` against all templates before deployment:

```bash
# Install
pip install cfn-lint

# Validate a template
cfn-lint cloudformation/backend-stack.yaml

# Validate with specific rules
cfn-lint cloudformation/backend-stack.yaml -e W
```

## SAM CLI Validation

Reference: SAM validate (https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/sam-cli-command-reference-sam-validate.html)

```bash
# Validate SAM template
sam validate --template cloudformation/backend-stack.yaml

# Validate with lint rules
sam validate --template cloudformation/backend-stack.yaml --lint
```

## SAM Local Testing

Reference: SAM local (https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/sam-cli-command-reference-sam-local-start-api.html)

Test Lambda handlers locally before deploying:

```bash
# Start local API
sam local start-api --template cloudformation/backend-stack.yaml \
  --parameter-overrides Environment=dev DbClusterArn=arn:... DbSecretArn=arn:... DbName=lms

# Invoke a single function
sam local invoke Create{Resource}Function \
  --event events/create-{resource}.json \
  --template cloudformation/backend-stack.yaml
```

## Change Set Validation

Reference: AWS CloudFormation change sets (https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/using-cfn-updating-stacks-changesets.html)

Before deploying to any environment, create a change set and review it:

```bash
aws cloudformation create-change-set \
  --stack-name lms-backend-dev \
  --template-body file://cloudformation/backend-stack.yaml \
  --change-set-name preview-$(date +%Y%m%d) \
  --parameters file://cloudformation/parameters/dev.json \
  --capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM

aws cloudformation describe-change-set \
  --stack-name lms-backend-dev \
  --change-set-name preview-$(date +%Y%m%d)
```

**Critical:** Always check for `Replacement: True` on stateful resources (RDS, S3) before executing a change set.

## CloudFormation Guard (Policy-as-Code)

Reference: CloudFormation Guard (https://docs.aws.amazon.com/cfn-guard/latest/ug/what-is-guard.html)

```bash
# Install
pip install cfn-guard

# Validate against rules
cfn-guard validate \
  --data cloudformation/backend-stack.yaml \
  --rules cloudformation/rules/security.guard
```

Example guard rules for this project:

```
# All Lambda functions must use arm64
AWS::Serverless::Function {
  Properties.Architectures[0] == "arm64"
}

# All Lambda functions must have a timeout <= 29 (API Gateway limit)
AWS::Serverless::Function {
  Properties.Timeout <= 29
}

# No wildcard IAM actions
AWS::IAM::Policy {
  Properties.PolicyDocument.Statement[*].Action[*] != "*"
}
```

## Template Checklist

- [ ] `cfn-lint` passes with no errors
- [ ] `sam validate` passes
- [ ] All parameters have `Description` and `AllowedValues` where applicable
- [ ] No hardcoded ARNs, account IDs, or region names
- [ ] Every Lambda has least-privilege IAM (only required actions + specific resources)
- [ ] API Gateway access logging enabled
- [ ] Log retention set explicitly on all log groups
- [ ] SQS queues: visibility timeout ≥ 6× Lambda timeout
- [ ] SQS consumers: `ReportBatchItemFailures` enabled
- [ ] DLQ wired with CloudWatch alarm at depth > 0
- [ ] Change set reviewed before deploying to staging/prod
- [ ] `DeletionPolicy: Retain` on stateful resources in prod
- [ ] Pseudo parameters used instead of hardcoded values (`AWS::Region`, `AWS::AccountId`, `AWS::StackName`)
- [ ] Outputs defined for values consumed by other stacks or the UI stack

## Gotchas

- This project uses CloudFormation/SAM — NOT CDK. Do not use `aws-cdk-lib/assertions`.
- SAM local requires Docker running locally.
- `cfn-lint` may not know about the latest SAM transform resources — use `--ignore-checks W` for SAM-specific warnings if needed.
- Change sets show resource replacements — always check for `Replacement: True` on stateful resources (RDS, S3) before deploying.
- API Gateway integration timeout max is 29 seconds — Lambda timeout must be ≤ 29s for synchronous API endpoints.

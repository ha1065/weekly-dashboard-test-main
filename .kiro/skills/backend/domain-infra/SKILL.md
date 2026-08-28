---
name: domain-infra
description: CloudFormation/SAM patterns for adding Lambda functions and API routes to the backend stack. Use when adding new endpoints or wiring up new domain infrastructure.
metadata:
  version: '1.0'
---

## Adding a New Endpoint

1. Create the handler at `backend/handlers/{domain}/{action}.ts`
2. Open `cloudformation/backend-stack.yaml`
3. Add a `AWS::Serverless::Function` resource for the handler
4. Add an API event to wire the Lambda to the API path + method
5. Grant any additional IAM permissions needed

## Lambda + API Route Pattern (SAM)

```yaml
Create{Domain}Function:
  Type: AWS::Serverless::Function
  Properties:
    Handler: handlers/{domain}/create.handler
    CodeUri: backend/
    Events:
      Create{Domain}:
        Type: Api
        Properties:
          RestApiId: !Ref LmsApi
          Path: /{domain}
          Method: POST
    Policies:
      - Statement:
          - Effect: Allow
            Action:
              - rds-data:ExecuteStatement
              - rds-data:BatchExecuteStatement
            Resource: !Ref DbClusterArn
          - Effect: Allow
            Action:
              - secretsmanager:GetSecretValue
            Resource: !Ref DbSecretArn
```

## Adding an SQS Consumer

For async message processing:

```yaml
{Domain}ProcessorFunction:
  Type: AWS::Serverless::Function
  Properties:
    Handler: handlers/{domain}/processor.handler
    CodeUri: backend/
    Events:
      {Domain}Queue:
        Type: SQS
        Properties:
          Queue: !GetAtt {Domain}Queue.Arn
          BatchSize: 10
          FunctionResponseTypes:
            - ReportBatchItemFailures
    Policies:
      - Statement:
          - Effect: Allow
            Action: [sqs:ReceiveMessage, sqs:DeleteMessage, sqs:GetQueueAttributes]
            Resource: !GetAtt {Domain}Queue.Arn
```

**`ReportBatchItemFailures` is mandatory** — without it, one failed message retries the entire batch.

## Gotchas

- This project uses CloudFormation/SAM. Do not use CDK or `aws-cdk-lib`.
- Each Lambda gets only the IAM permissions it needs — never `*` on actions or resources.
- Visibility timeout on SQS queues must be ≥ 6× the Lambda timeout.
- DLQ depth > 0 should trigger a CloudWatch alarm.
- All environment variables (DB ARNs, secret ARNs) come from CloudFormation parameters — never hardcoded.

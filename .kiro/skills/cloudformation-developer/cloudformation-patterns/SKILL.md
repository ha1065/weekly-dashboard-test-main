---
name: cloudformation-patterns
description: CloudFormation/SAM template patterns for the backend stack. Use when creating or modifying infrastructure templates.
metadata:
  version: '1.0'
---

## Template Structure

Reference: AWS CloudFormation template anatomy (https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/template-anatomy.html)
Reference: AWS SAM template anatomy (https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/sam-specification-template-anatomy.html)

```yaml
AWSTemplateFormatVersion: '2010-09-09'
Transform: AWS::Serverless-2016-10-31
Description: [Project] Backend Stack

Parameters:
  Environment:
    Type: String
    AllowedValues: [dev, qa, prod]
    Description: Deployment environment
  DbClusterArn:
    Type: String
    Description: RDS Aurora cluster ARN for Data API access
  DbSecretArn:
    Type: String
    Description: Secrets Manager ARN for database credentials
  DbName:
    Type: String
    Description: Database name

Globals:
  Function:
    Runtime: nodejs20.x
    Timeout: 30
    MemorySize: 256
    Architectures: [arm64]
    Environment:
      Variables:
        ENVIRONMENT: !Ref Environment
        DB_CLUSTER_ARN: !Ref DbClusterArn
        DB_SECRET_ARN: !Ref DbSecretArn
        DB_NAME: !Ref DbName
```

## Lambda Function Pattern

Reference: AWS::Serverless::Function (https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/sam-resource-function.html)

```yaml
Create{Resource}Function:
  Type: AWS::Serverless::Function
  Properties:
    Handler: handlers/{domain}/create.handler
    CodeUri: backend/
    Events:
      Create{Resource}:
        Type: Api
        Properties:
          RestApiId: !Ref LmsApi
          Path: /{resource}
          Method: POST
    Policies:
      - Statement:
          - Effect: Allow
            Action:
              - rds-data:ExecuteStatement
              - rds-data:BatchExecuteStatement
            Resource: !Ref DbClusterArn
          - Effect: Allow
            Action: secretsmanager:GetSecretValue
            Resource: !Ref DbSecretArn
```

## API Gateway Pattern

Reference: AWS::Serverless::Api (https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/sam-resource-api.html)

```yaml
LmsApi:
  Type: AWS::Serverless::Api
  Properties:
    StageName: !Ref Environment
    AccessLogSetting:
      DestinationArn: !GetAtt ApiAccessLogGroup.Arn
    MethodSettings:
      - HttpMethod: '*'
        ResourcePath: '/*'
        LoggingLevel: INFO

ApiAccessLogGroup:
  Type: AWS::Logs::LogGroup
  Properties:
    LogGroupName: !Sub '/aws/apigateway/${AWS::StackName}'
    RetentionInDays: 30
```

## CloudWatch Log Group Pattern

Reference: AWS CloudFormation best practices — log retention (https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/best-practices.html)

```yaml
{FunctionName}LogGroup:
  Type: AWS::Logs::LogGroup
  Properties:
    LogGroupName: !Sub '/aws/lambda/${Create{Resource}Function}'
    RetentionInDays: 30
```

## SQS Queue with DLQ Pattern

Reference: AWS::SQS::Queue (https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-sqs-queue.html)

```yaml
{Domain}Queue:
  Type: AWS::SQS::Queue
  Properties:
    QueueName: !Sub '${AWS::StackName}-{domain}-queue'
    VisibilityTimeout: 180  # Must be >= 6x Lambda timeout (30s * 6 = 180s)
    RedrivePolicy:
      deadLetterTargetArn: !GetAtt {Domain}DLQ.Arn
      maxReceiveCount: 3

{Domain}DLQ:
  Type: AWS::SQS::Queue
  Properties:
    QueueName: !Sub '${AWS::StackName}-{domain}-dlq'

{Domain}DLQAlarm:
  Type: AWS::CloudWatch::Alarm
  Properties:
    AlarmName: !Sub '${AWS::StackName}-{domain}-dlq-depth'
    MetricName: ApproximateNumberOfMessagesVisible
    Namespace: AWS/SQS
    Statistic: Sum
    Period: 300
    EvaluationPeriods: 1
    Threshold: 0
    ComparisonOperator: GreaterThanThreshold
    Dimensions:
      - Name: QueueName
        Value: !GetAtt {Domain}DLQ.QueueName
```

## Parameter File Pattern

```json
[
  { "ParameterKey": "Environment", "ParameterValue": "dev" },
  { "ParameterKey": "DbClusterArn", "ParameterValue": "arn:aws:rds:..." },
  { "ParameterKey": "DbSecretArn", "ParameterValue": "arn:aws:secretsmanager:..." },
  { "ParameterKey": "DbName", "ParameterValue": "lms_dev" }
]
```

## Key Rules

- Use `AWS::Serverless::Function` (SAM transform) for all Lambda definitions
- All environment-specific values via Parameters — never hardcoded
- Least-privilege IAM: each Lambda gets only the permissions it needs
- API Gateway access logging: always enabled
- Log retention: set explicitly (never leave as infinite)
- Removal policies: retain stateful resources in prod
- Use `!Sub` with pseudo parameters (`${AWS::Region}`, `${AWS::AccountId}`, `${AWS::StackName}`) for portability
- This project uses CloudFormation/SAM — NOT CDK. Do not use `aws-cdk-lib`.

## Gotchas

See `references/service-gotchas.md` for service-specific gotchas.

# CloudFormation Standards

Standards for writing AWS CloudFormation templates for the iCivics LMS platform.

**Note**: This project uses CloudFormation (not CDK). Cody confirmed: "We're using CloudFormation."

---

## 1. General Principles

- **CloudFormation YAML** — all infrastructure defined as YAML templates
- **SAM transform** — use `AWS::Serverless::Function` for Lambda definitions where it simplifies
- **Parameterized** — environment-specific values via parameter files, not hardcoded
- **Least privilege** — IAM roles scoped to exactly what each Lambda needs
- **Secrets via Secrets Manager** — never hardcode credentials; reference Secrets Manager ARNs

---

## 2. Stack Design

Two stacks (confirmed by Cody):

| Stack | Owner | Contents |
|-------|-------|----------|
| UI Stack | iCivics | S3 bucket, CloudFront CDN, Bitbucket pipeline deployment |
| Backend Stack | Cloudelligent | Lambda functions, API Gateway, IAM roles, Secrets Manager refs |

Cloudelligent only manages the Backend Stack. iCivics manages the UI deployment pipeline.

---

## 3. Project Structure

```
cloudformation/
├── backend-stack.yaml        # Main backend stack template
├── parameters/
│   ├── dev.json              # Dev environment parameters
│   ├── qa.json               # QA environment parameters
│   └── prod.json             # Prod environment parameters
└── scripts/
    └── deploy.sh             # Deployment helper script
```

---

## 4. Template Structure

```yaml
AWSTemplateFormatVersion: '2010-09-09'
Transform: AWS::Serverless-2016-10-31
Description: iCivics LMS Backend Stack

Parameters:
  Environment:
    Type: String
    AllowedValues: [dev, qa, prod]
  DbClusterArn:
    Type: String
  DbSecretArn:
    Type: String
  DbName:
    Type: String

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

Resources:
  # API Gateway
  LmsApi:
    Type: AWS::Serverless::Api
    Properties:
      StageName: !Ref Environment
      AccessLogSetting:
        DestinationArn: !GetAtt ApiAccessLogGroup.Arn

  # Lambda functions defined here...

Outputs:
  ApiEndpoint:
    Value: !Sub "https://${LmsApi}.execute-api.${AWS::Region}.amazonaws.com/${Environment}"
```

---

## 5. Lambda Function Pattern

```yaml
CreateClassFunction:
  Type: AWS::Serverless::Function
  Properties:
    Handler: handlers/classes/create.handler
    CodeUri: backend/
    Events:
      CreateClass:
        Type: Api
        Properties:
          RestApiId: !Ref LmsApi
          Path: /classes
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

---

## 6. Key Rules

- API Gateway access logging: **enabled** (confirmed by Cody)
- Lambda runtime: Node.js 20.x, ARM64 architecture
- All Lambda functions get RDS Data API + Secrets Manager permissions
- API Gateway endpoint provided to iCivics to add to `qa.app.icivics.org` CDN
- No VPC configuration needed for Lambda (RDS Data API is accessed over public AWS endpoints)
- CloudWatch Logs: enabled by default for all Lambda functions
- Alarm thresholds: pending Cloudelligent proposal to iCivics
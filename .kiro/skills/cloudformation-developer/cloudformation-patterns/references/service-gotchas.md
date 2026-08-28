# AWS Service-Specific Gotchas

## SQS Consumer

Reference: Amazon SQS visibility timeout (https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-visibility-timeout.html)

- **`reportBatchItemFailures: true` is mandatory.** Without it, one failed message retries the entire batch. Set this on every SQS event source mapping.
- **Visibility timeout ≥ 6× Lambda timeout.** If Lambda takes 30s, visibility timeout must be ≥ 180s. Otherwise SQS re-delivers the message while Lambda is still processing it.
- **DLQ alarm.** Wire a CloudWatch alarm on DLQ depth > 0. Silent DLQ accumulation is a production incident waiting to happen.
- **Idempotency.** SQS delivers at-least-once. Every consumer must be idempotent (safe to process the same message twice).
- **FIFO vs Standard.** FIFO guarantees order and exactly-once within a message group. Standard is higher throughput but unordered and at-least-once.

## API Gateway (REST)

Reference: API Gateway quotas and limits (https://docs.aws.amazon.com/apigateway/latest/developerguide/limits.html)

- **Binary media types.** If your API returns binary (images, PDFs), configure `binaryMediaTypes` on the API or responses will be base64-encoded strings.
- **Payload size limit.** API Gateway max request/response payload is 10 MB. Use S3 pre-signed URLs for large file uploads/downloads.
- **Timeout.** API Gateway max integration timeout is 29 seconds. Lambda must respond within 29s or the gateway returns 504.
- **CORS.** Configure CORS on the API Gateway resource AND return `Access-Control-Allow-Origin` from the Lambda response. Both are required.
- **Stage variables.** Use stage variables for environment-specific config (e.g., Lambda alias, backend URL). Don't hardcode env names in Lambda code.

## Lambda Function

Reference: Lambda best practices (https://docs.aws.amazon.com/lambda/latest/dg/best-practices.html)

- **Cold starts.** Minimize package size. Use Lambda layers for large shared dependencies. Keep handler initialization outside the handler function for reuse across invocations.
- **Concurrency limits.** Set reserved concurrency on critical functions to prevent noisy-neighbor throttling. Set it to 0 to disable a function without deleting it.
- **Environment variables.** Max 4 KB total. Use Secrets Manager for secrets, Parameter Store for config. Cache secrets at the module level (not inside the handler).
- **VPC cold starts.** Lambda in a VPC has longer cold starts. Only use VPC when the Lambda needs to access VPC-isolated resources (RDS, ElastiCache).
- **Execution role.** Least-privilege. Never use `AdministratorAccess` or `*` on actions/resources.

## EventBridge Rule

Reference: EventBridge event patterns (https://docs.aws.amazon.com/eventbridge/latest/userguide/eb-event-patterns.html)

- **Event pattern matching.** EventBridge pattern matching is exact — `"source": ["my.service"]` only matches that exact string. Use prefix matching (`"prefix": "my."`) for wildcards.
- **Dead-letter queue.** Add a DLQ to EventBridge rules for failed invocations. Without it, failed events are silently dropped.
- **Cross-account events.** Requires explicit resource-based policy on the target. Don't forget to add the event bus policy.
- **Schema registry.** Register event schemas in the EventBridge Schema Registry for discoverability and type generation.

## S3 Bucket

Reference: S3 security best practices (https://docs.aws.amazon.com/AmazonS3/latest/userguide/security-best-practices.html)

- **Block public access.** Enable all four block public access settings at the bucket level AND the account level.
- **Versioning.** Enable versioning on buckets that store user data or application state. Required for MFA delete.
- **Lifecycle rules.** Always define lifecycle rules — unchecked S3 growth is a common cost surprise.
- **Event notifications.** S3 event notifications are at-least-once. Consumers must be idempotent.
- **Pre-signed URLs.** Use pre-signed URLs for user uploads/downloads. Never expose bucket credentials to the client.
- **CORS.** Configure CORS on the bucket for browser-based uploads. Restrict `AllowedOrigins` to your domain — never use `*` for credentialed requests.

## CloudFormation-Specific

Reference: CloudFormation best practices (https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/best-practices.html)

- **DeletionPolicy.** Set `DeletionPolicy: Retain` on stateful resources (RDS, S3, DynamoDB) in production to prevent accidental data loss.
- **UpdateReplacePolicy.** Set `UpdateReplacePolicy: Retain` on stateful resources to prevent replacement during updates.
- **DependsOn.** Use `DependsOn` only when CloudFormation cannot infer the dependency from `!Ref` or `!GetAtt`. Overusing it creates unnecessary serialization.
- **Outputs.** Export values that other stacks need via `Outputs` with `Export`. Use `!ImportValue` in consuming stacks.
- **Nested stacks.** Use nested stacks when a single template exceeds ~200 resources or when you want to reuse a template across stacks.

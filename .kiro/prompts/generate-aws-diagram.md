I have a CloudFormation template below.

Please do the following:

1. Parse the template and identify all AWS resources, their types, and relationships
2. Use the AWS Documentation MCP to validate best practices for each service found
3. Generate an architecture diagram using the AWS Diagram MCP that shows:
   - Network boundaries (VPC, subnets - public vs private)
   - Compute layer (EC2, ECS, Lambda, etc.)
   - Data layer (RDS, DynamoDB, S3, ElastiCache, etc.)
   - Integration layer (SQS, SNS, EventBridge, API Gateway)
   - Edge layer (CloudFront, ALB, NLB, WAF)
   - Security boundaries (Security Groups, NACLs)
   - Resource relationships and traffic flow direction

Do NOT include any account IDs, real IP addresses, or sensitive values in the diagram labels.
Use generic, role-based labels only (e.g., "Web Tier ALB", "App Server", "Primary DB").

I'll provide you the template.

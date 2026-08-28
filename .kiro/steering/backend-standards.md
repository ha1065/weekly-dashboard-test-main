# Backend Development Standards

Standards for building serverless backend services for the iCivics LMS platform.

---

## 1. General Principles

- **Clarity over cleverness**: Readable code over clever abstractions
- **Explicit over implicit**: No magic — behavior should be obvious
- **Fail fast**: Errors are visible and actionable
- **Security by default**: Ownership checks on every mutation endpoint
- **Serverless-first**: Lambda, API Gateway, managed services — no containers in production

---

## 2. Technology Stack

| Layer         | Technology                                    |
| ------------- | --------------------------------------------- |
| Runtime       | Node.js LTS, TypeScript (strict mode)         |
| Compute       | AWS Lambda                                    |
| API           | API Gateway (REST)                            |
| Database      | RDS PostgreSQL via **RDS Data API**            |
| Auth          | iCivics-owned (read JWT tokens only)          |
| IaC           | **AWS CloudFormation** (not CDK)              |
| Validation    | Zod                                           |
| Secrets       | AWS Secrets Manager (cached at Lambda context) |
| Landing Pages | S3 JSON + CloudFront CDN                      |
| Analytics     | GA4 (frontend-only integration)               |
| Local Dev     | Docker PostgreSQL with migration scripts      |

**Not used**: Express.js, Fastify, NestJS, ECS, Kubernetes, MongoDB, DynamoDB, Cognito, OpenSearch, ElastiCache, SES, SNS.

**Note on ValKey**: iCivics uses Amazon MemoryDB (ValKey) for ranking/key-value. Connection details will be provided by iCivics. Not yet provisioned.

---

## 3. Project Structure

Monorepo with frontend and backend in the same LMS repository. The repo root **is** the frontend package.

```
icivics-lms/          # repo root = frontend SPA (package.json, vite.config.ts, src/ at root)
├── src/              # React frontend (TanStack Router, components, hooks, services)
├── backend/
│   ├── handlers/     # Lambda handler files (one per endpoint)
│   ├── services/     # Business logic layer
│   ├── db/           # Database query functions (RDS Data API)
│   ├── middleware/   # Auth token extraction, ownership checks, error handling
│   └── validation/  # Zod schemas
├── shared/
│   └── types/        # TypeScript types shared between frontend and backend
├── infrastructure/
│   ├── cloudformation.template.icivics-lms.yaml  # Backend stack
│   └── cloudformation.{env}.params.json          # Per-environment params
├── migrations/       # SQL migration scripts (numbered)
├── docker/           # Docker Compose (PostgreSQL + koxudaxi/local-data-api proxy)
├── specs/            # Implementation specs per story
└── docs/             # Architecture docs
```

---

## 4. Lambda Handler Pattern

```typescript
import { APIGatewayProxyEvent, APIGatewayProxyResult } from 'aws-lambda';
import { z } from 'zod';

const RequestSchema = z.object({
  title: z.string().min(1),
  class_id: z.number().int().positive(),
});

export const handler = async (
  event: APIGatewayProxyEvent
): Promise<APIGatewayProxyResult> => {
  try {
    const userId = extractUserId(event); // from auth token
    const body = RequestSchema.parse(JSON.parse(event.body ?? '{}'));
    const result = await createAssignment(userId, body);
    return { statusCode: 201, body: JSON.stringify(result) };
  } catch (error) {
    return handleError(error);
  }
};
```

Key rules:
- One handler per Lambda function, one Lambda per API endpoint
- Validate input with Zod at the boundary
- Extract user identity from auth token headers
- Enforce ownership checks (e.g., only class owner can modify class)
- Return machine-readable error codes in response body

---

## 5. Database Access — RDS Data API

iCivics uses **RDS Data API** (not direct PostgreSQL connections). This means:
- No connection pooling needed
- No VPC Lambda configuration for DB access
- Use `@aws-sdk/client-rds-data` to execute SQL
- Parameterized queries only — never string interpolation

```typescript
import { RDSDataClient, ExecuteStatementCommand } from '@aws-sdk/client-rds-data';

const client = new RDSDataClient({});

// Initialize at module level (Lambda context), not per invocation
const resourceArn = process.env.DATA_API_RESOURCE_ARN!;
const secretArn = process.env.DATA_API_SECRET_ARN!;
const database = process.env.DATA_API_DATABASE!;

export async function getClassById(classId: number) {
  const result = await client.send(new ExecuteStatementCommand({
    resourceArn,
    secretArn,
    database,
    sql: 'SELECT * FROM "Classes" WHERE class_id = :classId AND deleted = false',
    parameters: [{ name: 'classId', value: { longValue: classId } }],
  }));
  return result.records;
}
```

---

## 6. Secrets Management

- All secrets stored in **AWS Secrets Manager**
- Secrets are injected during CloudFormation build
- If pulled at runtime, cache at Lambda context level (module scope) — NOT per invocation
- Environment variables for ARNs: `DATA_API_RESOURCE_ARN`, `DATA_API_SECRET_ARN`, `DATA_API_DATABASE`

---

## 7. CloudFormation Standards

- All infrastructure defined in CloudFormation/SAM YAML
- Two stacks: UI stack (iCivics manages) + Backend stack (Cloudelligent manages)
- Backend stack includes: Lambda functions, API Gateway, IAM roles, Secrets Manager references
- Use `AWS::Serverless::Function` (SAM transform) for Lambda definitions where possible
- API Gateway access logging: enabled (confirmed by Cody)
- Parameter files per environment (dev, qa, prod)

---

## 8. API Design

- RESTful endpoints via API Gateway
- ~20 CRUD endpoints total
- Standard HTTP status codes: 200, 201, 400, 401, 403, 404, 409, 500
- Error response format:
  ```json
  { "code": "CLASS_NOT_FOUND", "message": "Class with id 123 not found" }
  ```
- Ownership enforcement: every mutation checks requesting user owns the resource

---

## 9. Key Endpoints (from User Stories US-010 to US-032)

**User Service:**
- `GET /users/{id}` — get profile
- `PUT /users/{id}` — partial profile update
- `POST /users/{id}/reroll-username` — generate new unique username
- `DELETE /users/{id}` — soft-delete (cancel account)

**Classes:**
- `POST /classes` — create class (auto-generate class_code)
- `GET /classes/users/{uid}` — list classes for user
- `GET /classes/{id}/students` — list students in class
- `PUT /classes/{id}` — update class
- `PUT /classes/{id}/archive` | `PUT /classes/{id}/unarchive`
- `DELETE /classes/{id}` — soft-delete class
- `POST /classes/{id}/reset-passwords` — bulk reset student passwords
- `POST /classes/{id}/students/reset-password` — single student password reset
- `GET /classes/{id}/students/export` — CSV download
- `DELETE /classes/{id}/students/{studentId}` — remove student
- `POST /classes/{id}/students/bulk` — bulk add students
- `POST /classes/join` — student joins class via class_code

**Assignments:**
- `POST /assignments` | `GET /assignments?class_id={id}` | `PUT /assignments/{id}` | `DELETE /assignments/{id}` (soft-delete)
- `GET /assignments/{id}/results` — per-student progress
- `GET /assignments/{id}/results/export` — export results
- `PUT /assignments/{id}/students/{studentId}/status` — update student assignment status
- `GET /users/{id}/outstanding-assignments` — outstanding assignments for student
- `GET /classes/{classId}/students/{studentId}/assignments` — list assignments for student in class
- `GET /classes/{classId}/students/{studentId}/view` — view class as student

**Other:**
- `GET /users/{id}/achievements` — earned achievements
- `POST /users/{id}/favorites` | `DELETE /users/{id}/favorites/{resourceId}` | `GET /users/{id}/favorites`
- `GET /users/{id}/activity` — activity feed (separate Postgres instance)

---

## 10. Testing

- Unit tests for service layer functions
- Integration tests for Lambda handlers with mocked RDS Data API
- Local development: Docker Compose with PostgreSQL + migration scripts
- SQL migrations: numbered files (`001_create_users.sql`, `002_create_classes.sql`, etc.)

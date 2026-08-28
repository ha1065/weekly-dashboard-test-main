---
name: lambda-handler-patterns
version: 1.0
description: Lambda handler patterns for iCivics LMS using RDS Data API. Use when creating or modifying any Lambda handler.
---

## Handler Structure

One handler per file, one Lambda per API endpoint. Handlers are thin — validate input, extract auth, call service, return response.

```typescript
// backend/handlers/classes/create.ts
import { APIGatewayProxyEvent, APIGatewayProxyResult } from 'aws-lambda';
import { CreateClassSchema } from '../../validation/classSchemas';
import { extractUserId } from '../../middleware/auth';
import { handleError } from '../../middleware/errorHandler';
import { createClass } from '../../services/classService';

export const handler = async (
  event: APIGatewayProxyEvent,
): Promise<APIGatewayProxyResult> => {
  try {
    const userId = extractUserId(event);
    const body = CreateClassSchema.parse(JSON.parse(event.body ?? '{}'));
    const result = await createClass(userId, body);
    return { statusCode: 201, body: JSON.stringify(result) };
  } catch (error) {
    return handleError(error);
  }
};
```

## File Naming

- File name = action verb: `create.ts`, `get.ts`, `update.ts`, `archive.ts`, `delete.ts`
- Path = `backend/handlers/{domain}/{action}.ts`
- Examples: `handlers/classes/create.ts`, `handlers/assignments/getResults.ts`, `handlers/favorites/add.ts`

## Auth Extraction

```typescript
// backend/middleware/auth.ts
import { APIGatewayProxyEvent } from 'aws-lambda';
import { verify } from 'jsonwebtoken';

export interface AuthContext {
  uid: string;
  grants: string[]; // deserialized in handlers from authorizer context
}

export function extractAuthContext(event: APIGatewayProxyEvent): AuthContext {
  const authHeader = event.headers['Authorization'] || event.headers['authorization'];
  if (!authHeader) throw new AppError(401, 'UNAUTHORIZED', 'Missing authorization header');
  const token = authHeader.replace('Bearer ', '');

  let payload: any;
  const secret = process.env.JWT_SECRET;
  if (secret) {
    // Production: verify signature
    payload = verify(token, secret) as any;
  } else {
    // QA: decode only (no signature verification)
    const base64Payload = token.split('.')[1];
    payload = JSON.parse(atob(base64Payload));
  }

  const uid = payload.uid ?? payload.sub;
  if (!uid) throw new AppError(401, 'UNAUTHORIZED', 'No user identity in token');
  return { uid: String(uid), grants: payload.grants ?? [] };
}

// Convenience wrapper for handlers that only need uid
export function extractUserId(event: APIGatewayProxyEvent): string {
  return extractAuthContext(event).uid;
}
```

> **QA vs Production:** QA: JWT_SECRET env var is empty — Lambda decodes without verification. Production: JWT_SECRET is set in Secrets Manager — Lambda verifies signature. Zero code changes between environments.

> **Authorizer context serialization:** When used in the Lambda Authorizer itself, serialize grants before returning context: `grants: JSON.stringify(payload.grants ?? [])`. In domain Lambda handlers reading from authorizer context, deserialize: `const grants = JSON.parse(event.requestContext.authorizer?.grants ?? "[]")`.

### Role Classification

```typescript
// Role classification from JWT grants (no DB query needed)
export function isTeacher(grants: string[]): boolean {
  return grants.includes('cta.teach');
}
export function isStudent(grants: string[]): boolean {
  return grants.includes('cta.playLearn');
}
```

> Role determination uses JWT grants array — no user_to_role DB query needed at middleware layer. DB ownership checks (Classes.owner_uid, etc.) are still required for resource-level authorization.

## Ownership Checks

Every mutation endpoint must verify the requesting user owns the resource:

```typescript
// backend/middleware/ownership.ts
import { ForbiddenError } from './errorHandler';

export function assertClassOwner(classOwnerId: number, requestingUserId: number): void {
  if (classOwnerId !== requestingUserId) {
    throw new ForbiddenError('NOT_CLASS_OWNER', 'Only the class owner can perform this action');
  }
}
```

## Path Parameters and Query Strings

```typescript
const classId = parseInt(event.pathParameters?.id ?? '', 10);
if (isNaN(classId)) {
  throw new ValidationError('Invalid class ID');
}

const studentId = event.queryStringParameters?.studentId;
```

## Response Patterns

| Action | Status | Body |
|--------|--------|------|
| Create | 201 | Created resource |
| Read | 200 | Resource or array |
| Update | 200 | Updated resource |
| Delete (soft) | 200 | `{ "deleted": true }` |
| List (empty) | 200 | `[]` (not 404) |

## Gotchas

- Handlers should be ~15 lines max — delegate to service layer
- Always parse `event.body` with `JSON.parse()` then validate with Zod
- Path parameters are always strings — parse to `number` with `parseInt` and validate
- Return `[]` for empty lists, not 404
- Soft-delete assignments (set `deleted = true`), archive classes (set `is_archived = true`)
- `resource_identifier` is an integer (node_id) — use the corrected column name, not the ERD typo

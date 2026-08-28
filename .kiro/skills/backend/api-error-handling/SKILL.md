---
name: api-error-handling
version: 1.0
description: API error response format, error classes, and status codes for iCivics Lambda handlers. Use when creating or modifying error handling in any Lambda handler.
---

## Error Response Shape

Every error response follows this format:

```json
{
  "code": "CLASS_NOT_FOUND",
  "message": "Class with id 123 not found"
}
```

- `code`: Machine-readable error identifier (UPPER_SNAKE_CASE)
- `message`: Human-readable description

## Status Code Mapping

| Status | When | Example Code |
|--------|------|-------------|
| 400 | Validation failure, bad input | `VALIDATION_ERROR`, `INVALID_DUE_DATE` |
| 401 | Missing or expired auth token | `UNAUTHORIZED` |
| 403 | Authenticated but not authorized (not the owner) | `NOT_CLASS_OWNER`, `NOT_ENROLLED` |
| 404 | Resource not found | `CLASS_NOT_FOUND`, `ASSIGNMENT_NOT_FOUND` |
| 409 | Conflict (e.g., joining archived class) | `CLASS_ARCHIVED`, `DUPLICATE_FAVORITE` |
| 500 | Unexpected server error | `INTERNAL_ERROR` |

## Error Classes

```typescript
export class AppError extends Error {
  constructor(
    public statusCode: number,
    public code: string,
    message: string,
  ) {
    super(message);
  }
}

export class NotFoundError extends AppError {
  constructor(resource: string, id: string | number) {
    super(404, `${resource.toUpperCase()}_NOT_FOUND`, `${resource} with id ${id} not found`);
  }
}

export class ValidationError extends AppError {
  constructor(message: string) {
    super(400, 'VALIDATION_ERROR', message);
  }
}

export class ForbiddenError extends AppError {
  constructor(code: string, message: string) {
    super(403, code, message);
  }
}

export class ConflictError extends AppError {
  constructor(code: string, message: string) {
    super(409, code, message);
  }
}
```

## Error Handler Middleware

```typescript
import { APIGatewayProxyResult } from 'aws-lambda';
import { ZodError } from 'zod';

export function handleError(error: unknown): APIGatewayProxyResult {
  if (error instanceof AppError) {
    return {
      statusCode: error.statusCode,
      body: JSON.stringify({ code: error.code, message: error.message }),
    };
  }

  if (error instanceof ZodError) {
    return {
      statusCode: 400,
      body: JSON.stringify({
        code: 'VALIDATION_ERROR',
        message: error.errors.map(e => `${e.path.join('.')}: ${e.message}`).join('; '),
      }),
    };
  }

  console.error('Unexpected error:', error);
  return {
    statusCode: 500,
    body: JSON.stringify({ code: 'INTERNAL_ERROR', message: 'An unexpected error occurred' }),
  };
}
```

## Gotchas

- Never return raw error messages from unknown errors — always use generic "An unexpected error occurred"
- Zod validation errors should be caught and re-formatted with field paths
- 401 = missing/expired token only; 403 = authenticated but lacking access (wrong owner, not enrolled)
- Always include machine-readable `code` field — frontend uses it for conditional UI logic
- Log the full error to CloudWatch before returning the sanitized response

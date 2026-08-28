# Lambda Documentation Standards

## Three-Tier Strategy

| Tier             | What                                                  | Where                         |
| ---------------- | ----------------------------------------------------- | ----------------------------- |
| OpenAPI spec     | API endpoints, request/response schemas, error codes  | `specs/api/{domain}.yaml`     |
| TypeScript types | Data structures, function signatures                  | `shared/types/`               |
| Domain README    | Purpose, env vars, IAM permissions                    | `docs/domain-{n}-*-architecture.md` |

---

## Handler Template

```typescript
import { APIGatewayProxyEvent, APIGatewayProxyResult } from 'aws-lambda';
import { CreateClassSchema } from '../../validation/classSchemas';
import { extractUserId } from '../../middleware/auth';
import { handleError } from '../../middleware/errorHandler';
import { createClass } from '../../services/classService';

/**
 * Create a new class.
 * @see specs/api/classes.yaml#/paths/~1classes/post
 */
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

---

## JSDoc Rules

- Every handler: **one-line JSDoc** referencing its OpenAPI spec — nothing more
- No `@param event`, `@returns Promise<...>` — TypeScript types handle this
- Complex business logic (algorithms, eligibility rules): JSDoc explaining WHY, not WHAT
- OpenAPI specs are the single source of truth for API contracts — do not duplicate in JSDoc

---

## File Structure

```
backend/
├── handlers/{domain}/    # Lambda entry points (thin — ~15 lines max)
├── services/             # Business logic
├── db/                   # RDS Data API query functions
├── middleware/           # Auth (extractUserId), ownership checks, error handling
├── validation/           # Zod schemas
└── __tests__/            # Tests
shared/
└── types/                # TypeScript types shared between frontend and backend
specs/api/
└── {domain}.yaml         # OpenAPI spec (generated during implementation)
```

---

## Code Review Checklist

- [ ] TypeScript types defined in `shared/types/`
- [ ] OpenAPI spec updated in `specs/api/`
- [ ] Handler is thin (~15 lines) — business logic in service layer
- [ ] One-line JSDoc only — no verbose documentation in handler
- [ ] No hardcoded secrets — env vars only (`DATA_API_RESOURCE_ARN`, `DATA_API_SECRET_ARN`, `DATA_API_DATABASE`)
- [ ] Ownership check present on all mutation endpoints

---

## Mandatory Requirements

1. **TypeScript strict mode** for all Lambdas
2. **OpenAPI spec** for every API endpoint (`specs/api/{domain}.yaml`)
3. **Minimal JSDoc** — one-liner referencing OpenAPI spec only
4. **Zod validation** at handler boundary
5. **Parameterized SQL** — never string interpolation

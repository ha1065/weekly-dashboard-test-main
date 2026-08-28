---
name: aurora-rls-patterns
description: RDS Data API query patterns for iCivics LMS. Use when writing database queries, creating migrations, or working with the RDS PostgreSQL database via the RDS Data API.
metadata:
  version: '1.0'
---

## RDS Data API Query Pattern

iCivics uses the **RDS Data API** — no direct PostgreSQL connections, no connection pooling, no VPC Lambda config needed.

```typescript
import { RDSDataClient, ExecuteStatementCommand } from '@aws-sdk/client-rds-data';

// Initialize at module level (reused across Lambda invocations)
const rdsClient = new RDSDataClient({ region: process.env.AWS_REGION });

export async function queryDb<T>(sql: string, parameters: SqlParameter[] = []): Promise<T[]> {
  const command = new ExecuteStatementCommand({
    resourceArn: process.env.DB_CLUSTER_ARN,
    secretArn: process.env.DB_SECRET_ARN,
    database: process.env.DB_NAME,
    sql,
    parameters,
    formatRecordsAs: 'JSON',
  });
  const result = await rdsClient.send(command);
  return JSON.parse(result.formattedRecords ?? '[]') as T[];
}
```

## Parameterized Queries

Always use the `parameters` array — never string interpolation:

```typescript
import { SqlParameter } from '@aws-sdk/client-rds-data';

// ✅ Correct — parameterized
const classes = await queryDb<Class>(
  'SELECT * FROM "Classes" WHERE teacher_id = :teacherId AND is_archived = :archived',
  [
    { name: 'teacherId', value: { longValue: userId } },
    { name: 'archived', value: { booleanValue: false } },
  ],
);

// ❌ Wrong — SQL injection risk
const classes = await queryDb(`SELECT * FROM "Classes" WHERE teacher_id = ${userId}`);
```

## Parameter Types

| TypeScript type | RDS Data API field |
|----------------|-------------------|
| `number` (integer) | `{ longValue: n }` |
| `number` (float) | `{ doubleValue: n }` |
| `string` | `{ stringValue: s }` |
| `boolean` | `{ booleanValue: b }` |
| `null` | `{ isNull: true }` |
| UUID string | `{ stringValue: uuid }` |

## Creating a Migration

1. Find the next sequence number in `migrations/` (e.g., `V015__`)
2. Create file: `V{NNN}__{description}.sql`
3. Use `PascalCase` for table names (matching existing iCivics ERD convention), `snake_case` for columns
4. Include `created_at`, `updated_at`, `deleted` columns where applicable

```sql
-- V015__create_resource_notes.sql
CREATE TABLE "ResourceNotes" (
  id SERIAL PRIMARY KEY,
  resource_id INTEGER NOT NULL REFERENCES "Resources"(id),
  note_text TEXT NOT NULL,
  created_by INTEGER NOT NULL REFERENCES "Users"(id),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  deleted BOOLEAN NOT NULL DEFAULT false
);
```

## Soft Delete Pattern

iCivics uses soft deletes — never `DELETE FROM`:

```typescript
// Soft delete
await queryDb(
  'UPDATE "Assignments" SET deleted = true, updated_at = now() WHERE id = :id AND teacher_id = :teacherId',
  [
    { name: 'id', value: { longValue: assignmentId } },
    { name: 'teacherId', value: { longValue: userId } },
  ],
);

// Always filter deleted rows in SELECT queries
const assignments = await queryDb<Assignment>(
  'SELECT * FROM "Assignments" WHERE class_id = :classId AND deleted = false',
  [{ name: 'classId', value: { longValue: classId } }],
);
```

## Ownership Check Pattern

Verify the requesting user owns the resource before mutating:

```typescript
const [cls] = await queryDb<{ teacher_id: number }>(
  'SELECT teacher_id FROM "Classes" WHERE id = :id',
  [{ name: 'id', value: { longValue: classId } }],
);

if (!cls) throw new NotFoundError('Class', classId);
if (cls.teacher_id !== userId) throw new ForbiddenError('NOT_CLASS_OWNER', 'Only the class owner can perform this action');
```

## Gotchas

- Initialize `RDSDataClient` at **module level**, not inside the handler — Lambda reuses the execution context across invocations.
- `formatRecordsAs: 'JSON'` returns a JSON string in `formattedRecords` — parse it with `JSON.parse()`.
- Table names in iCivics use `PascalCase` with double quotes (e.g., `"Classes"`, `"Assignments"`) — always quote them.
- The column is `resource_identifier` (integer node_id) — not `resource_id`. This is a known ERD naming quirk.
- Migrations are **forward-only** — never edit a deployed migration file. Create a new `V{N+1}__fix_{description}.sql` instead.
- `due_date` must be in the future — validate this in the service layer before inserting.

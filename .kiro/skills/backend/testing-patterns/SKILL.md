---
name: testing-patterns
version: 1.0
description: Backend testing patterns for iCivics Lambda handlers and services using RDS Data API mocking. Use when writing unit or integration tests.
---

## Service Unit Tests

Location: `backend/__tests__/services/`

Mock the RDS Data API client and test business logic:

```typescript
// backend/__tests__/services/classService.test.ts
import { RDSDataClient, ExecuteStatementCommand } from '@aws-sdk/client-rds-data';
import { mockClient } from 'aws-sdk-client-mock';
import { createClass } from '../../services/classService';

const rdsMock = mockClient(RDSDataClient);

beforeEach(() => {
  rdsMock.reset();
});

describe('createClass', () => {
  it('creates a class with auto-generated class code', async () => {
    rdsMock.on(ExecuteStatementCommand).resolves({
      records: [[
        { longValue: 1 },           // class_id
        { stringValue: 'ABC123' },   // class_code
      ]],
    });

    const result = await createClass(42, { title: 'Civics 101', default_password: 'pass123' });

    expect(result.class_id).toBe(1);
    expect(result.class_code).toBeDefined();

    const call = rdsMock.commandCalls(ExecuteStatementCommand)[0];
    expect(call.args[0].input.sql).toContain('INSERT INTO "Classes"');
  });

  it('rejects assignment with past due date', async () => {
    await expect(
      createAssignment(42, { title: 'Test', due_date: '2020-01-01', class_id: 1, resource_identifier: 100 })
    ).rejects.toThrow('INVALID_DUE_DATE');
  });
});
```

## Handler Integration Tests

Location: `backend/__tests__/handlers/`

Build a fake API Gateway event and test the full handler:

```typescript
// backend/__tests__/handlers/classes/create.test.ts
import { handler } from '../../../handlers/classes/create';
import { mockClient } from 'aws-sdk-client-mock';
import { RDSDataClient, ExecuteStatementCommand } from '@aws-sdk/client-rds-data';

const rdsMock = mockClient(RDSDataClient);

function buildEvent(body: object, userId = 42): any {
  return {
    body: JSON.stringify(body),
    headers: { Authorization: `Bearer mock-token-for-uid-${userId}` },
    pathParameters: null,
    queryStringParameters: null,
  };
}

describe('POST /classes', () => {
  beforeEach(() => rdsMock.reset());

  it('returns 201 with created class', async () => {
    rdsMock.on(ExecuteStatementCommand).resolves({
      records: [[{ longValue: 1 }, { stringValue: 'XYZ789' }]],
    });

    const result = await handler(buildEvent({ title: 'Civics 101', default_password: 'pass' }));

    expect(result.statusCode).toBe(201);
    const body = JSON.parse(result.body);
    expect(body.class_code).toBeDefined();
  });

  it('returns 400 for missing title', async () => {
    const result = await handler(buildEvent({ default_password: 'pass' }));
    expect(result.statusCode).toBe(400);
    expect(JSON.parse(result.body).code).toBe('VALIDATION_ERROR');
  });

  it('returns 401 for missing auth header', async () => {
    const event = { body: '{}', headers: {}, pathParameters: null, queryStringParameters: null };
    const result = await handler(event as any);
    expect(result.statusCode).toBe(401);
  });
});
```

## Key Libraries

- `aws-sdk-client-mock` — mock RDS Data API client (SDK v3 compatible)
- `jest` — test runner
- No need to mock VPC or network — RDS Data API is HTTP-based

## Gotchas

- Always mock `RDSDataClient` at module level with `mockClient()`, reset in `beforeEach`
- Auth token extraction needs to be mockable — either mock the `extractUserId` function or build events with test tokens
- Test both success and error paths for every handler
- Test ownership checks: call with wrong userId, expect 403
- Test soft-delete: verify `deleted = true` is set, not row removal
- RDS Data API returns records in a specific format — mock that format exactly

---
name: domain-hooks
description: Domain hook patterns for API data fetching. Use when creating or updating hooks that fetch, mutate, or cache domain data from the backend API.
metadata:
  version: '1.0'
---

## Pattern 1: RTK Query (preferred for complex domains)

Use RTK Query when a domain has multiple endpoints, needs cache invalidation, or shares data across many components.

### API Slice

```typescript
// hooks/[domain]Api.ts
import { createApi } from '@reduxjs/toolkit/query/react';
import { baseQuery } from '../shared/baseQuery';
import type { [Resource], Create[Resource]Request } from '@[project]/shared/types';

export const [domain]Api = createApi({
  reducerPath: '[domain]Api',
  baseQuery,
  tagTypes: ['[Resource]'],
  endpoints: (builder) => ({
    list[Resources]: builder.query<[Resource][], void>({
      query: () => '/api/[domain]',
      providesTags: ['[Resource]'],
    }),
    get[Resource]: builder.query<[Resource], string>({
      query: (id) => `/api/[domain]/${id}`,
      providesTags: (_result, _error, id) => [{ type: '[Resource]', id }],
    }),
    create[Resource]: builder.mutation<[Resource], Create[Resource]Request>({
      query: (body) => ({ url: '/api/[domain]', method: 'POST', body }),
      invalidatesTags: ['[Resource]'],
    }),
    update[Resource]: builder.mutation<[Resource], { id: string; data: Partial<[Resource]> }>({
      query: ({ id, data }) => ({ url: `/api/[domain]/${id}`, method: 'PATCH', body: data }),
      invalidatesTags: (_result, _error, { id }) => [{ type: '[Resource]', id }, '[Resource]'],
    }),
  }),
});

export const {
  useList[Resources]Query,
  useGet[Resource]Query,
  useCreate[Resource]Mutation,
  useUpdate[Resource]Mutation,
} = [domain]Api;
```

### Adding a New Endpoint

1. Add the endpoint definition to the `endpoints` builder
2. Export the generated hook from the api slice
3. Add `providesTags` on queries and `invalidatesTags` on mutations to keep cache consistent

## Pattern 2: useApiClient (simpler domains)

Use `useApiClient` for domains with few endpoints or one-off fetches that don't need shared caching.

```typescript
// hooks/use[Domain].ts
import { useState, useEffect } from 'react';
import { useApiClient } from '../shared/useApiClient';
import type { [Resource] } from '@[project]/shared/types';

export function use[Domain]() {
  const api = useApiClient();
  const [resources, setResources] = useState<[Resource][]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchResources = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await api.get<[Resource][]>('/api/[domain]');
      setResources(data);
    } catch (err) {
      setError('Failed to load [resources]');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => { fetchResources(); }, []);

  return { resources, isLoading, error, refetch: fetchResources };
}
```

## Cache Invalidation Rules

- After a `create` mutation: invalidate the list tag (`'[Resource]'`)
- After an `update` mutation: invalidate both the specific item tag and the list tag
- After a `delete` mutation: invalidate the list tag
- Never manually update the cache — always invalidate and let RTK Query refetch

## Gotchas

- Never call `fetch` directly in components — always go through a domain hook or RTK Query
- Types must come from the shared types package — never define API response types inline in hooks
- RTK Query hooks return `{ data, isLoading, isError, error }` — always handle all three states in the component
- `providesTags` and `invalidatesTags` must be symmetric — if a query provides `[{ type: 'X', id }]`, mutations must invalidate `[{ type: 'X', id }]`

---
name: page-routing
description: Frontend page routing and navigation patterns. Use when adding new pages, route groups, layouts, or navigation flows.
metadata:
  version: '1.0'
---

## Route Structure

Organize routes by user role or feature area using route groups:

```
src/
  pages/
    (auth)/           # Unauthenticated routes (login, register, forgot-password)
      login/
      register/
    (app)/            # Authenticated routes (require login)
      dashboard/
      [domain]/
        index/        # List view
        [id]/         # Detail view
        new/          # Create form
    (admin)/          # Admin-only routes
      users/
      settings/
```

## Adding a New Page

1. Create the page component in the appropriate route group
2. Add the route to the router configuration
3. Wrap with `ProtectedRoute` if authentication is required
4. Add a navigation link if the page should appear in the nav

```typescript
// router.tsx
const router = createBrowserRouter([
  {
    path: '/',
    element: <RootLayout />,
    children: [
      { path: 'login', element: <LoginPage /> },
      {
        element: <ProtectedRoute />,
        children: [
          { path: 'dashboard', element: <DashboardPage /> },
          { path: '[domain]', element: <[Domain]ListPage /> },
          { path: '[domain]/:id', element: <[Domain]DetailPage /> },
          { path: '[domain]/new', element: <[Domain]CreatePage /> },
        ],
      },
    ],
  },
]);
```

## Layout Pattern

Use nested layouts to share UI between related pages:

```typescript
// layouts/AppLayout.tsx
export function AppLayout() {
  return (
    <div className="flex h-screen">
      <Sidebar />
      <main className="flex-1 overflow-auto">
        <TopBar />
        <div className="p-6">
          <Outlet /> {/* child pages render here */}
        </div>
      </main>
    </div>
  );
}
```

## Navigation

Use the router's `navigate` function or `<Link>` component — never `window.location.href` for in-app navigation:

```typescript
// ✅ Correct
import { useNavigate, Link } from 'react-router-dom';

const navigate = useNavigate();
navigate('/dashboard');
<Link to="/dashboard">Go to Dashboard</Link>

// ❌ Wrong
window.location.href = '/dashboard'; // loses React state, causes full page reload
```

## Programmatic Navigation After Mutation

```typescript
const [createResource] = useCreateResourceMutation();
const navigate = useNavigate();

const handleSubmit = async (data: CreateResourceRequest) => {
  const result = await createResource(data).unwrap();
  navigate(`/[domain]/${result.id}`); // redirect to detail page after create
};
```

## Gotchas

- Always use `replace: true` when redirecting after login/logout to prevent the auth page from appearing in browser history
- Lazy-load heavy pages with `React.lazy()` and `<Suspense>` to reduce initial bundle size
- Route params are always strings — parse/validate them before use (e.g., `parseInt(params.id)` or UUID validation)
- 404 handling: add a catch-all route at the end of the router config
- Deep links: ensure the server serves `index.html` for all routes (SPA fallback config)

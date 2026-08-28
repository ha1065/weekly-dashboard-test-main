---
name: auth-patterns
description: Frontend authentication patterns — token storage, protected routes, auth flow, and provider tree. Use when implementing login, MFA, session management, or protected pages.
metadata:
  version: '1.0'
---

## Auth Flow

```
Login form → POST /auth/login
  → success: store tokens, redirect to intended page
  → MFA required: redirect to MFA challenge page
  → error: show inline error message

MFA challenge → POST /auth/mfa/verify
  → success: store tokens, redirect to intended page
  → error: show inline error, allow retry (max 3 attempts)

Token refresh → POST /auth/token/refresh (automatic, via API client interceptor)
  → success: update stored access token
  → failure (refresh expired): clear tokens, redirect to login
```

## Token Storage Rules

| Token | Storage | Rationale |
|-------|---------|-----------|
| Access token | Memory (React state / context) | Short-lived, never persisted to disk |
| ID token | Memory (React state / context) | Contains PII — never in localStorage |
| Refresh token | `localStorage` (if remember-me) or session memory | Longer-lived, survives page refresh |

**Never store access or ID tokens in `localStorage` or `sessionStorage`** — XSS can read them.

## Protected Route Pattern

```typescript
// components/ProtectedRoute.tsx
export function ProtectedRoute({ children, requiredRoles }: ProtectedRouteProps) {
  const { user, isLoading } = useAuth();
  const location = useLocation();

  if (isLoading) return <LoadingSpinner />;

  if (!user) {
    return <Navigate to="/login" state={{ returnUrl: location.pathname }} replace />;
  }

  if (requiredRoles && !requiredRoles.some(role => user.roles.includes(role))) {
    return <Navigate to="/unauthorized" replace />;
  }

  return <>{children}</>;
}
```

## Return URL Pattern

After login, redirect the user back to where they were trying to go:

```typescript
// On login success:
const { returnUrl } = location.state ?? {};
navigate(returnUrl ?? '/dashboard', { replace: true });
```

## Auth Provider Tree Position

The auth provider must wrap the entire app, above the router:

```typescript
// main.tsx
<AuthProvider>
  <BrowserRouter>
    <App />
  </BrowserRouter>
</AuthProvider>
```

## Gotchas

- Never redirect to an arbitrary `returnUrl` from query params — validate it's a relative path to prevent open redirect attacks.
- Clear all tokens on logout — both memory state and localStorage.
- Handle token expiry gracefully: the API client should auto-refresh before the access token expires (e.g., refresh when < 60s remaining).
- MFA state must not persist across page refreshes — store it in memory only.
- On 401 from API: attempt one token refresh, then redirect to login if refresh fails.

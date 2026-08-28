# Frontend Development Standards

Standards for building the iCivics LMS frontend — a React SPA with TypeScript.

---

## 1. General Principles

- **Figma first**: Before building any page, confirm the Figma design is finalized. Do not build from assumptions.
- **Design system**: Use the shared UI component library from Phase 1 (resource-library repo). Import shared components — do not duplicate.
- **Clarity over cleverness**: Readable components over clever abstractions
- **Accessible by default**: WCAG 2.1 AA compliance on all interactive elements
- **Type-safe**: TypeScript strict mode, shared types with backend

---

## 2. Technology Stack

| Layer      | Technology                                |
| ---------- | ----------------------------------------- |
| Framework  | React 18+ (SPA — no SSR)                 |
| Bundler    | Vite                                      |
| Language   | TypeScript (strict mode)                  |
| Routing    | React Router v6                           |
| State      | React Context + hooks for local state     |
| API Client | fetch or lightweight wrapper              |
| Forms      | React Hook Form + Zod validation          |
| Styling    | CSS Modules or styled approach per Figma  |
| Analytics  | GA4 (gtag.js) — UTM pass-through only    |
| Testing    | Jest + React Testing Library              |
| Deployment | S3 + CloudFront (iCivics manages pipeline)|

**Not used**: Next.js, MUI, Redux/RTK, Tailwind CSS (unless confirmed by Figma/design system).

**Note**: The exact UI library/design system will be confirmed once Figma designs are finalized (expected May 15). Until then, build with semantic HTML and CSS Modules that can be reskinned.

---

## 3. Project Structure

```
frontend/
├── public/                   # Static assets (favicon, icons)
├── src/
│   ├── components/           # Shared UI components
│   │   ├── Button/
│   │   ├── Card/
│   │   ├── Modal/
│   │   └── Layout/
│   ├── pages/
│   │   ├── teacher/          # Teacher LMS pages
│   │   │   ├── Home/
│   │   │   ├── Classes/
│   │   │   ├── ClassDetail/
│   │   │   ├── Assignments/
│   │   │   ├── AssignmentResults/
│   │   │   ├── Students/
│   │   │   ├── Profile/
│   │   │   ├── Favorites/
│   │   │   └── StatePortal/
│   │   ├── student/          # Student LMS pages
│   │   │   ├── Home/
│   │   │   ├── Classes/
│   │   │   ├── ClassDetail/
│   │   │   ├── Achievements/
│   │   │   ├── ActivityFeed/
│   │   │   └── Profile/
│   │   └── landing/          # Public landing pages (Phase 4)
│   │       ├── PlayAndLearn/
│   │       └── Teach/
│   ├── hooks/                # Custom hooks (useAuth, useApi, etc.)
│   ├── api/                  # API client functions
│   ├── types/                # Shared TypeScript types
│   ├── utils/                # Utility functions
│   ├── context/              # React Context providers (Auth, etc.)
│   ├── App.tsx
│   ├── main.tsx
│   └── router.tsx            # Route definitions
├── index.html
├── vite.config.ts
├── tsconfig.json
└── package.json
```

---

## 4. Page Inventory (15 LMS pages + 2 landing pages)

### Teacher Pages (~9)
1. Teacher Home (after login)
2. Edit Profile + Avatar
3. Favorites
4. State Portal (4 states, hardcoded JSON)
5. Classes Overview (active + archived)
6. Class Detail (Assignments tab + Students tab)
7. Create/Edit Assignment
8. Assignment Results (3 design patterns, games has 2 variants)
9. View as Student (teacher sees student's LMS home)

### Student Pages (~6)
1. Student Home (with outstanding assignments indicator)
2. Edit Profile + Avatar
3. Activity Feed (chronological)
4. Achievements
5. Classes Overview
6. Class Detail (assignments for that class)

### Landing Pages (Phase 4 — ~2)
1. Play & Learn (header redesign, featured 3 items, video playlists)
2. Teach (Why/How/What sections, logged-in variant removes Why/How)

---

## 5. Auth Integration

- Auth is **owned by iCivics** — frontend does NOT implement login/registration flows
- Frontend reads auth tokens from iCivics auth system
- Use an `AuthContext` provider that exposes: `user`, `isAuthenticated`, `token`
- Pass token in API requests via `Authorization` header
- Role-based UI: show/hide elements based on user role (teacher vs student)
- Avatar creator is an existing React widget from iCivics — embed it, don't rebuild

---

## 6. API Integration

```typescript
const API_BASE = import.meta.env.VITE_API_BASE_URL;

async function apiClient<T>(path: string, options?: RequestInit): Promise<T> {
  const token = getAuthToken();
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(token && { Authorization: `Bearer ${token}` }),
      ...options?.headers,
    },
  });
  if (!response.ok) {
    const error = await response.json();
    throw new ApiError(response.status, error.code, error.message);
  }
  return response.json();
}
```

---

## 7. Landing Pages (Phase 4)

- Content loaded from **S3 JSON** (not API/database)
- UTM parameters: read from URL query params, pass to GA4 gtag — do NOT persist in cookies/session
- SEO: semantic HTML, Open Graph meta tags, proper heading hierarchy
- CDN-delivered via CloudFront (iCivics manages CDN config)
- State portals: load hardcoded JSON file per state (4 states)

---

## 8. Component Guidelines

- One component per file
- Co-locate styles: `ComponentName.module.css` next to `ComponentName.tsx`
- Props interfaces defined and exported
- Use semantic HTML elements (`<nav>`, `<main>`, `<section>`, `<article>`)
- All interactive elements must have accessible labels
- Loading states: use skeleton/spinner components
- Empty states: show meaningful messages (not blank screens)
- Error states: show user-friendly error messages with retry option

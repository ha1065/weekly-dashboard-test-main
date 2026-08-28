---
name: design-system
description: Design system and component theming patterns. Use when creating UI components, applying theme tokens, or extending the design system.
metadata:
  version: '1.0'
---

## Using Theme Tokens

Always use design system tokens instead of hardcoded values. This ensures consistency and supports theming (light/dark mode, brand customization).

```typescript
// ✅ Correct — uses theme tokens
import { useTheme } from '@/hooks/useTheme';

function MyComponent() {
  const theme = useTheme();
  return (
    <div style={{
      color: theme.colors.text.primary,
      backgroundColor: theme.colors.background.surface,
      padding: theme.spacing(2),
      borderRadius: theme.borderRadius.md,
    }}>
      Content
    </div>
  );
}

// ❌ Wrong — hardcoded values
function MyComponent() {
  return <div style={{ color: '#333', padding: '16px' }}>Content</div>;
}
```

## Creating a New Component

1. Check if a similar component already exists in the design system
2. If extending an existing component, use composition — don't modify the base component
3. Accept a `className` prop for consumer overrides
4. Export from the design system index

```typescript
// components/design-system/StatusBadge.tsx
import { cn } from '@/utils/cn';

type Status = 'active' | 'inactive' | 'pending';

interface StatusBadgeProps {
  status: Status;
  className?: string;
}

const statusStyles: Record<Status, string> = {
  active: 'bg-green-100 text-green-800',
  inactive: 'bg-gray-100 text-gray-600',
  pending: 'bg-yellow-100 text-yellow-800',
};

export function StatusBadge({ status, className }: StatusBadgeProps) {
  return (
    <span className={cn('inline-flex items-center px-2 py-1 rounded text-sm font-medium', statusStyles[status], className)}>
      {status}
    </span>
  );
}
```

## Spacing System

Use the spacing scale consistently. The base unit is 4px:

| Token | Value |
|-------|-------|
| spacing(0.5) | 2px |
| spacing(1) | 4px |
| spacing(2) | 8px |
| spacing(3) | 12px |
| spacing(4) | 16px |
| spacing(6) | 24px |
| spacing(8) | 32px |

Never use arbitrary pixel values — always use the spacing scale.

## Typography

Use semantic typography variants, not raw font sizes:

```typescript
// ✅ Correct
<h1 className="text-heading-xl">Page Title</h1>
<p className="text-body-md">Body text</p>
<span className="text-label-sm">Form label</span>

// ❌ Wrong
<h1 style={{ fontSize: '32px', fontWeight: 700 }}>Page Title</h1>
```

## Gotchas

- Never mix design system components with raw HTML elements that duplicate their purpose (e.g., don't use `<button>` when a `Button` component exists)
- Don't use inline styles for anything that belongs in the theme — inline styles can't be overridden by themes
- Component variants should be defined as props, not as separate components (e.g., `<Button variant="primary">` not `<PrimaryButton>`)
- Always test components in both light and dark mode if the project supports theming
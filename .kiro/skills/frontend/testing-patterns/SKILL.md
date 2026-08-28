---
name: testing-patterns
version: 1.0
description: Frontend testing patterns for iCivics React components and hooks. Use when writing Jest component tests, hook tests, or integration tests.
---

## Component Tests

Location: `frontend/src/__tests__/components/` or co-located as `ComponentName.test.tsx`

```typescript
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ClassCard } from '../components/Card/ClassCard';

describe('ClassCard', () => {
  const mockClass = {
    class_id: 1,
    title: 'Civics 101',
    class_code: 'ABC123',
    assignment_count: 5,
    student_count: 20,
    is_archived: false,
  };

  it('renders class title and code', () => {
    render(<ClassCard classData={mockClass} />);
    expect(screen.getByText('Civics 101')).toBeInTheDocument();
    expect(screen.getByText('ABC123')).toBeInTheDocument();
  });

  it('shows archived badge when class is archived', () => {
    render(<ClassCard classData={{ ...mockClass, is_archived: true }} />);
    expect(screen.getByText('Archived')).toBeInTheDocument();
  });

  it('calls onView when view button is clicked', async () => {
    const onView = jest.fn();
    render(<ClassCard classData={mockClass} onView={onView} />);
    await userEvent.click(screen.getByRole('button', { name: /view/i }));
    expect(onView).toHaveBeenCalledWith(1);
  });
});
```

## Hook Tests

```typescript
import { renderHook, waitFor } from '@testing-library/react';
import { useClasses } from '../hooks/useClasses';

// Mock the API client
jest.mock('../api/classes', () => ({
  getClasses: jest.fn(),
}));

import { getClasses } from '../api/classes';

describe('useClasses', () => {
  it('returns classes on success', async () => {
    (getClasses as jest.Mock).mockResolvedValue([
      { class_id: 1, title: 'Civics 101' },
    ]);

    const { result } = renderHook(() => useClasses());

    await waitFor(() => {
      expect(result.current.classes).toHaveLength(1);
      expect(result.current.isLoading).toBe(false);
    });
  });

  it('handles error state', async () => {
    (getClasses as jest.Mock).mockRejectedValue(new Error('Network error'));

    const { result } = renderHook(() => useClasses());

    await waitFor(() => {
      expect(result.current.error).toBeTruthy();
      expect(result.current.isLoading).toBe(false);
    });
  });
});
```

## Selector Priorities

Use in this order (most accessible first):
1. `getByRole` — buttons, links, headings, textboxes
2. `getByLabelText` — form fields
3. `getByText` — visible text content
4. `getByTestId` — last resort only

## Gotchas

- Use `userEvent` (not `fireEvent`) for user interactions — it simulates real browser behavior
- Always wrap state updates in `waitFor` or use `findBy` queries
- Mock API calls at the module level with `jest.mock()`
- Test loading, success, empty, and error states for every data-fetching component
- Run accessibility checks where possible — ensure interactive elements have accessible names
- Don't test CSS/styling — test behavior and content

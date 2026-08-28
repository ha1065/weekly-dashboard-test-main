---
name: form-patterns
version: 1.0
description: React Hook Form + Zod form patterns for iCivics. Use when building forms for class creation, assignment creation, profile editing, or student bulk add.
---

## Basic Form Pattern

```typescript
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';

const CreateClassSchema = z.object({
  title: z.string().min(1, 'Class title is required'),
  default_password: z.string().min(4, 'Password must be at least 4 characters'),
});

type CreateClassForm = z.infer<typeof CreateClassSchema>;

export function CreateClassForm({ onSubmit }: { onSubmit: (data: CreateClassForm) => void }) {
  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<CreateClassForm>({
    resolver: zodResolver(CreateClassSchema),
  });

  return (
    <form onSubmit={handleSubmit(onSubmit)}>
      <label htmlFor="title">
        Class Title <span aria-hidden="true">*</span>
      </label>
      <input id="title" {...register('title')} aria-required="true" />
      {errors.title && <p role="alert">{errors.title.message}</p>}

      <label htmlFor="default_password">
        Default Student Password <span aria-hidden="true">*</span>
      </label>
      <input id="default_password" type="password" {...register('default_password')} aria-required="true" />
      {errors.default_password && <p role="alert">{errors.default_password.message}</p>}

      <button type="submit" disabled={isSubmitting}>
        {isSubmitting ? 'Creating...' : 'Create Class'}
      </button>
    </form>
  );
}
```

## Assignment Form with Date Validation

```typescript
const CreateAssignmentSchema = z.object({
  title: z.string().min(1, 'Title is required'),
  description: z.string().optional(),
  resource_identifier: z.number().int().positive('Resource is required'),
  due_date: z.string().refine(
    (date) => new Date(date) > new Date(),
    'Due date must be in the future',
  ),
});
```

## Form with API Submission

```typescript
export function CreateClassPage() {
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();

  const onSubmit = async (data: CreateClassForm) => {
    try {
      setError(null);
      const result = await api.classes.create(data);
      navigate(`/classes/${result.class_id}`);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError('An unexpected error occurred');
      }
    }
  };

  return (
    <>
      {error && <div role="alert">{error}</div>}
      <CreateClassForm onSubmit={onSubmit} />
    </>
  );
}
```

## Gotchas

- Always use `zodResolver` — never validate manually
- Required fields need both `*` visual indicator AND `aria-required="true"`
- Error messages displayed below the field with `role="alert"`
- Disable submit button while `isSubmitting` to prevent double-submit
- Due date validation: reject past dates (business rule from Kevin)
- Show API errors above the form, field errors below each field
- Use `<label htmlFor>` — never rely on placeholder text as the label

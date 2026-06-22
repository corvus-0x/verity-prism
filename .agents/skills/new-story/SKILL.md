---
name: new-story
description: Scaffold a Storybook story file for a Verity Prism component — finds the component, reads its interface, and writes a complete .stories.jsx with correct tags, ✓/⚠ naming, and stress tests. Invoke as /new-story ComponentName.
---

The user has invoked `/new-story <ComponentName>`. Your job is to produce a complete, ready-to-run Storybook story file for that component.

## Steps

1. **Find the component.** Search `frontend/src/components/` and `frontend/src/pages/` for a file named `<ComponentName>.jsx`. Read it fully to understand its props, what data it renders, and what states it can be in.

2. **Identify the states.** Before writing a single line of the story, answer these questions explicitly:
   - What props does it accept? What are the types and defaults?
   - What does it look like when content is long / data is excessive?
   - What does it look like when the container is narrow (200–280px)?
   - What does it look like when it's empty or receives null?
   - Are there multiple visual variants (status, severity, type)?

3. **Write the story file** at `frontend/src/stories/<ComponentName>.stories.jsx`.

## Required structure

Every story file must have:

```jsx
import { ComponentName } from '../components/path/ComponentName'  // adjust path

export default {
  title: 'Section/ComponentName',   // Section = Core, Documents, Layout, etc.
  component: ComponentName,
  tags: ['ai-generated', 'needs-work'],  // always start with needs-work
  parameters: { layout: 'centered' },   // or 'fullscreen' for full-page components
}
```

### Required story types

| Story name | Prefix | What it proves |
|---|---|---|
| Default / happy path | `✓` | Component renders correctly with typical data |
| All variants / all statuses | `✓` | Every variant is visible at once |
| Long content | `⚠` | Text wraps or truncates gracefully, doesn't overflow |
| Narrow container (200px) | `⚠` | Renders inside `<div style={{ width: '200px' }}>` |
| Empty / null input | `⚠` | Component doesn't crash with no data |

If the component has interactive behavior (click, edit, form), add a `play` function to the default story that asserts the behavior using `canvas` and `expect` from `'storybook/test'`.

### CssCheck (add to one story per file if testing a styled element)

```jsx
export const CssCheck = {
  name: '⚠ CSS loaded check',
  render: () => <ComponentName />,
  play: async ({ canvas }) => {
    const el = canvas.getByRole('...')
    // Assert a specific computed style from the design system
    await expect(getComputedStyle(el).backgroundColor).toBe('rgb(...)')
  },
}
```

## After writing

Tell the user:
1. Where the file was created
2. Run: `cd frontend && npx vitest --workspace vitest.workspace.js --project storybook run`
3. When tests pass, remove `'needs-work'` from the tags array

## Design system reference

CSS classes available (defined in `frontend/src/index.css`):
- `btn-primary` — signal red button, white text
- `btn-ghost` — ghost button, slate border
- `field-input` — dark input with red focus ring
- `surface-card` — dark card with hover lift
- `nav-link` / `nav-link-active` — sidebar nav items
- `mono-val` — JetBrains Mono for data values

Colors (Tailwind): `slate-900` = `#040810`, `slate-800` = `#0C1424`, `slate-400` = `#5C7A9B`, `red-600` = `#DC2626`

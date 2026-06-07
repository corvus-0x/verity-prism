import { expect } from 'storybook/test'

export default {
  title: 'Core/Buttons',
  tags: ['ai-generated'],
  parameters: { layout: 'centered' },
}

export const AllVariants = {
  name: '✓ All button variants',
  render: () => (
    <div className="flex flex-col gap-6 w-64">
      <div className="flex flex-col gap-2">
        <span className="text-slate-400 text-xs uppercase tracking-widest">Primary</span>
        <button className="btn-primary">+ New Workspace</button>
        <button className="btn-primary" disabled>Disabled</button>
        <button className="btn-primary w-full">Full width</button>
      </div>
      <div className="flex flex-col gap-2">
        <span className="text-slate-400 text-xs uppercase tracking-widest">Ghost</span>
        <button className="btn-ghost">Cancel</button>
        <button className="btn-ghost" disabled>Disabled</button>
        <button className="btn-ghost w-full">Full width</button>
      </div>
    </div>
  ),
}

// CssCheck — proves the shared preview actually loaded the design system CSS.
// btn-primary uses background: #991B1B → rgb(153, 27, 27)
export const CssCheck = {
  name: '⚠ CSS loaded (design system check)',
  render: () => <button className="btn-primary">Sign In</button>,
  play: async ({ canvas }) => {
    const button = canvas.getByRole('button', { name: /sign in/i })
    await expect(getComputedStyle(button).backgroundColor).toBe('rgb(153, 27, 27)')
  },
}

export const LongLabel = {
  name: '⚠ Long label (stress test)',
  render: () => (
    <div className="flex flex-col gap-3 w-48">
      <button className="btn-primary">Export all workspace extractions as CSV</button>
      <button className="btn-ghost">Cancel and discard all unsaved changes</button>
    </div>
  ),
}

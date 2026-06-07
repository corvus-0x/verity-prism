import Badge from '../components/shared/Badge'

export default {
  title: 'Core/Badge',
  component: Badge,
  tags: ['ai-generated'],
  parameters: { layout: 'centered' },
}

export const AllStatuses = {
  name: '✓ All statuses',
  render: () => (
    <div className="flex flex-wrap gap-3">
      {['active', 'complete', 'pending', 'needs_review', 'no_schema', 'failed',
        'open', 'confirmed', 'closed', 'critical', 'high', 'medium', 'low'].map(s => (
        <div key={s} className="flex flex-col items-center gap-1">
          <Badge label={s} />
          <span className="text-slate-500" style={{ fontSize: '9px' }}>{s}</span>
        </div>
      ))}
    </div>
  ),
}

export const UnknownLabel = {
  name: '⚠ Unknown label (fallback)',
  render: () => <Badge label="something_unexpected" />,
}

export const EmptyLabel = {
  name: '⚠ Empty / null label',
  render: () => <Badge label={null} />,
}

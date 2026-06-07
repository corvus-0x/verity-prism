import LoadingSpinner from '../components/shared/LoadingSpinner'

export default {
  title: 'Core/LoadingSpinner',
  component: LoadingSpinner,
  tags: ['ai-generated'],
  parameters: { layout: 'centered' },
}

export const Default = {
  name: '✓ Default',
}

export const InsideNarrowContainer = {
  name: '⚠ Inside narrow container (200px)',
  render: () => (
    <div style={{ width: '200px', border: '1px solid #1A2A3F' }}>
      <LoadingSpinner />
    </div>
  ),
}

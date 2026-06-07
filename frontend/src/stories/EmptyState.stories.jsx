import EmptyState from '../components/shared/EmptyState'

export default {
  title: 'Core/EmptyState',
  component: EmptyState,
  tags: ['ai-generated'],
}

export const WithAction = {
  name: '✓ With action button',
  args: {
    message: 'No documents yet.',
    action: 'Upload your first document',
    onAction: () => {},
  },
}

export const MessageOnly = {
  name: '✓ Message only (no action)',
  args: { message: 'No workspaces yet. Create one to get started.' },
}

export const LongMessage = {
  name: '⚠ Long message (stress test)',
  args: {
    message: 'No documents match your current filter. Try clearing the status filter or uploading additional documents to this workspace.',
    action: 'Clear filters',
    onAction: () => {},
  },
}

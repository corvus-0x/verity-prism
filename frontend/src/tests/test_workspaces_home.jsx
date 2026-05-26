import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import WorkspacesHome from '../pages/WorkspacesHome'

test('displays list of workspaces', async () => {
  render(<MemoryRouter><WorkspacesHome /></MemoryRouter>)
  await waitFor(() =>
    expect(screen.getByText('Do Good In His Name Inc')).toBeInTheDocument()
  )
})

test('shows Karen Homan as subject', async () => {
  render(<MemoryRouter><WorkspacesHome /></MemoryRouter>)
  await waitFor(() =>
    expect(screen.getByText(/karen homan/i)).toBeInTheDocument()
  )
})

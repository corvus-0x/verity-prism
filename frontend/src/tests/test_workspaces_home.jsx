import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import WorkspacesHome from '../pages/WorkspacesHome'

test('displays list of workspaces', async () => {
  render(<MemoryRouter><WorkspacesHome /></MemoryRouter>)
  await waitFor(() =>
    expect(screen.getByText('Bright Future Ministries Inc')).toBeInTheDocument()
  )
})

test('shows Sarah Mitchell as subject', async () => {
  render(<MemoryRouter><WorkspacesHome /></MemoryRouter>)
  await waitFor(() =>
    expect(screen.getByText(/sarah mitchell/i)).toBeInTheDocument()
  )
})

import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { http, HttpResponse } from 'msw'
import { server } from './mocks/server'
import AIChat from '../pages/workspace/AIChat'
import { ToastProvider } from '../hooks/useToast'

function renderChat() {
  return render(
    <ToastProvider>
      <MemoryRouter initialEntries={['/workspaces/ws-1/chat']}>
        <Routes>
          <Route path="/workspaces/:workspaceId/chat" element={<AIChat />} />
        </Routes>
      </MemoryRouter>
    </ToastProvider>
  )
}

beforeEach(() => {
  server.use(
    http.get('/workspaces/ws-1/conversations', () =>
      HttpResponse.json([{ id: 'conv-1', title: null, workspace_id: 'ws-1' }])
    ),
    http.get('/workspaces/ws-1/conversations/conv-1/messages', () =>
      HttpResponse.json([])
    ),
  )
})

test('rolls back optimistic message when sendMessage fails', async () => {
  server.use(
    http.post('/workspaces/ws-1/conversations/conv-1/messages', () =>
      HttpResponse.json({ detail: 'Server error' }, { status: 500 })
    )
  )

  renderChat()
  await waitFor(() => screen.getByRole('textbox'))

  await userEvent.type(screen.getByRole('textbox'), 'Will this fail?')
  await userEvent.click(screen.getByRole('button', { name: /send/i }))

  await waitFor(() =>
    expect(screen.queryByText('Will this fail?')).not.toBeInTheDocument()
  )
})

test('shows error toast when sendMessage fails', async () => {
  server.use(
    http.post('/workspaces/ws-1/conversations/conv-1/messages', () =>
      HttpResponse.json({ detail: 'Server error' }, { status: 500 })
    )
  )

  renderChat()
  await waitFor(() => screen.getByRole('textbox'))

  await userEvent.type(screen.getByRole('textbox'), 'This will error')
  await userEvent.click(screen.getByRole('button', { name: /send/i }))

  await waitFor(() =>
    expect(screen.getByText(/send failed/i)).toBeInTheDocument()
  )
})

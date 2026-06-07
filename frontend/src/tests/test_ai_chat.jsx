import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { http, HttpResponse } from 'msw'
import { server } from './mocks/server'
import AIChat from '../pages/workspace/AIChat'
import { ToastProvider } from '../hooks/useToast'

server.use(
  http.get('/workspaces/ws-1/conversations', () => HttpResponse.json([])),
)

test('shows new conversation button', async () => {
  render(
    <ToastProvider>
      <MemoryRouter initialEntries={['/workspaces/ws-1/chat']}>
        <Routes>
          <Route path="/workspaces/:workspaceId/chat" element={<AIChat />} />
        </Routes>
      </MemoryRouter>
    </ToastProvider>
  )
  await waitFor(() =>
    expect(screen.getByText(/new conversation/i)).toBeInTheDocument()
  )
})

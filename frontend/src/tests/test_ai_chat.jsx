import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { http, HttpResponse } from 'msw'
import { server } from './mocks/server'
import AIChat from '../pages/workspace/AIChat'

server.use(
  http.get('/workspaces/ws-1/conversations', () => HttpResponse.json([])),
)

test('shows new conversation button', async () => {
  render(
    <MemoryRouter initialEntries={['/workspaces/ws-1/chat']}>
      <Routes>
        <Route path="/workspaces/:workspaceId/chat" element={<AIChat />} />
      </Routes>
    </MemoryRouter>
  )
  await waitFor(() =>
    expect(screen.getByText(/new conversation/i)).toBeInTheDocument()
  )
})

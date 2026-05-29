import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { http, HttpResponse } from 'msw'
import { server } from './mocks/server'
import Documents from '../pages/workspace/Documents'
import { ToastProvider } from '../hooks/useToast'

const renderDocuments = () =>
  render(
    <ToastProvider>
      <MemoryRouter initialEntries={['/workspaces/ws-1/documents']}>
        <Routes>
          <Route path="/workspaces/:workspaceId/documents" element={<Documents />} />
        </Routes>
      </MemoryRouter>
    </ToastProvider>
  )

test('shows upload area', async () => {
  server.use(
    http.get('/workspaces/ws-1/documents', () => HttpResponse.json([]))
  )
  renderDocuments()
  await waitFor(() =>
    expect(screen.getByText(/drag and drop/i)).toBeInTheDocument()
  )
})

test('displays document list', async () => {
  server.use(
    http.get('/workspaces/ws-1/documents', () =>
      HttpResponse.json([{
        id: 'doc-1',
        filename: '2022-09-15_DEED_DoGoodRealEstate_47-Patterson.pdf',
        original_filename: 'scan0047.pdf',
        detected_doc_type: 'DEED',
        extraction_status: 'complete',
        uploaded_at: '2026-01-01T00:00:00Z',
      }])
    )
  )
  renderDocuments()
  await waitFor(() =>
    expect(screen.getByText(/2022-09-15_DEED/)).toBeInTheDocument()
  )
})

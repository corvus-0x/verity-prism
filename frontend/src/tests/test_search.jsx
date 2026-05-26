import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { http, HttpResponse } from 'msw'
import { server } from './mocks/server'
import Search from '../pages/workspace/Search'

const renderSearch = () =>
  render(
    <MemoryRouter initialEntries={['/workspaces/ws-1/search']}>
      <Routes>
        <Route path="/workspaces/:workspaceId/search" element={<Search />} />
      </Routes>
    </MemoryRouter>
  )

test('shows search input', () => {
  renderSearch()
  expect(screen.getByPlaceholderText(/plain english/i)).toBeInTheDocument()
})

test('displays results after search', async () => {
  server.use(
    http.post('/workspaces/ws-1/search', () =>
      HttpResponse.json({
        query: 'deeds with zero consideration',
        result_count: 1,
        results: [{
          document_id: 'doc-1',
          filename: '2023-09-22_DEED_Mescher_13-Trinity-Zero.pdf',
          detected_doc_type: 'DEED',
          matched_fields: { consideration_amount: '0', grantee_name: 'Mescher Family' },
        }]
      })
    )
  )
  renderSearch()
  const input = screen.getByPlaceholderText(/plain english/i)
  await userEvent.type(input, 'deeds with zero consideration')
  await userEvent.click(screen.getByRole('button', { name: /search/i }))
  await waitFor(() =>
    expect(screen.getAllByText(/Mescher/).length).toBeGreaterThan(0)
  )
})

import { http, HttpResponse } from 'msw'

export const handlers = [
  http.post('/auth/login', () => {
    return HttpResponse.json({ access_token: 'test-token', token_type: 'bearer' })
  }),
  http.get('/workspaces/', () => {
    return HttpResponse.json([
      {
        id: 'ws-1',
        name: 'Do Good In His Name Inc',
        subject_name: 'Karen Homan',
        vertical: 'fraud',
        status: 'active',
        created_at: '2026-01-01T00:00:00Z',
        updated_at: '2026-01-01T00:00:00Z',
      }
    ])
  }),
]

import { http, HttpResponse } from 'msw'

export const handlers = [
  http.post('/auth/login', () => {
    return HttpResponse.json({
      access_token: 'test-token',
      token_type: 'bearer',
      user: {
        id: 'user-1',
        email: 'analyst@example.com',
        full_name: 'Test Analyst',
        role: 'investigator',
        created_at: '2026-01-01T00:00:00Z',
      },
    })
  }),
  http.get('/auth/me', () => {
    // Default: 401 — tests that need authenticated session override this
    return HttpResponse.json({ detail: 'Not authenticated' }, { status: 401 })
  }),
  http.post('/auth/logout', () => {
    return HttpResponse.json({ message: 'Logged out' })
  }),
  http.get('/workspaces/', () => {
    return HttpResponse.json([
      {
        id: 'ws-1',
        name: 'Bright Future Ministries Inc',
        subject_name: 'Sarah Mitchell',
        vertical: 'fraud',
        status: 'active',
        created_at: '2026-01-01T00:00:00Z',
        updated_at: '2026-01-01T00:00:00Z',
      }
    ])
  }),
]

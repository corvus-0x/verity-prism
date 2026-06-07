import { http, HttpResponse } from 'msw'

const mockUser = { id: 'story-user', email: 'dev@verityprsim.local', role: 'admin' }

export const mswHandlers = {
  auth: [
    http.get('/auth/me', () => HttpResponse.json(mockUser)),
    http.post('/auth/login', () => HttpResponse.json({ user: mockUser })),
    http.post('/auth/logout', () => HttpResponse.json({ ok: true })),
  ],
  workspaces: [
    http.get('/workspaces', () => HttpResponse.json([])),
  ],
}

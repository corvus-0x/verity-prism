import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { http, HttpResponse } from 'msw'
import { server } from './mocks/server'
import Login from '../pages/Login'

const renderLogin = () =>
  render(<MemoryRouter><Login /></MemoryRouter>)

test('renders email and password fields', () => {
  renderLogin()
  expect(screen.getByPlaceholderText(/email/i)).toBeInTheDocument()
  expect(screen.getByPlaceholderText(/password/i)).toBeInTheDocument()
})

test('shows error on wrong credentials', async () => {
  server.use(
    http.post('/auth/login', () =>
      HttpResponse.json({ detail: 'Invalid credentials' }, { status: 401 })
    )
  )
  renderLogin()
  fireEvent.change(screen.getByPlaceholderText(/email/i), {
    target: { value: 'wrong@example.com' }
  })
  fireEvent.change(screen.getByPlaceholderText(/password/i), {
    target: { value: 'wrongpass' }
  })
  fireEvent.click(screen.getByRole('button', { name: /sign in/i }))
  await waitFor(() =>
    expect(screen.getByText(/invalid credentials/i)).toBeInTheDocument()
  )
})

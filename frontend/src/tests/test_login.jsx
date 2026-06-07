import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { http, HttpResponse } from 'msw'
import { server } from './mocks/server'
import Login from '../pages/Login'
import useAuthStore from '../store/auth'

const renderLogin = () =>
  render(<MemoryRouter><Login /></MemoryRouter>)

test('renders email and password fields', () => {
  renderLogin()
  expect(screen.getByLabelText(/email/i)).toBeInTheDocument()
  expect(screen.getByLabelText(/password/i)).toBeInTheDocument()
})

test('stores user in auth store on successful login', async () => {
  renderLogin()
  fireEvent.change(screen.getByLabelText(/email/i), {
    target: { value: 'tyler@example.com' },
  })
  fireEvent.change(screen.getByLabelText(/password/i), {
    target: { value: 'correctpass' },
  })
  fireEvent.click(screen.getByRole('button', { name: /sign in/i }))

  await waitFor(() => {
    const { user } = useAuthStore.getState()
    expect(user).not.toBeNull()
    expect(user.email).toBe('tyler@example.com')
  })
})

test('shows error on wrong credentials', async () => {
  server.use(
    http.post('/auth/login', () =>
      HttpResponse.json({ detail: 'Invalid credentials' }, { status: 401 })
    )
  )
  renderLogin()
  fireEvent.change(screen.getByLabelText(/email/i), {
    target: { value: 'wrong@example.com' }
  })
  fireEvent.change(screen.getByLabelText(/password/i), {
    target: { value: 'wrongpass' }
  })
  fireEvent.click(screen.getByRole('button', { name: /sign in/i }))
  await waitFor(() =>
    expect(screen.getByText(/invalid credentials/i)).toBeInTheDocument()
  )
})

import client from './client'

export const register = (email, password, fullName) =>
  client.post('/auth/register', { email, password, full_name: fullName })

export const login = (email, password) =>
  client.post('/auth/login', { email, password })

export const logout = () =>
  client.post('/auth/logout')

export const me = () =>
  client.get('/auth/me')

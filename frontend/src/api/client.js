import axios from 'axios'
import useAuthStore from '../store/auth'

let _navigate = null

/**
 * Called once from NavigatorSetter inside BrowserRouter.
 * Gives the 401 interceptor access to React Router navigation without
 * importing useNavigate outside component scope.
 */
export function setNavigate(navigate) {
  _navigate = navigate
}

const client = axios.create({
  baseURL: '/',
  headers: { 'Content-Type': 'application/json' },
  withCredentials: true,
})

client.interceptors.request.use((config) => {
  const token = useAuthStore.getState().token
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

client.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      useAuthStore.getState().logout()
      if (_navigate) {
        _navigate('/login', { replace: true })
      } else {
        window.location.href = '/login'
      }
    }
    return Promise.reject(error)
  }
)

export default client

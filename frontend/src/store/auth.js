import { create } from 'zustand'

const useAuthStore = create((set) => ({
  user: null,
  token: null,  // kept for test backward compat (auth_headers fixture uses Bearer)
  setUser: (user) => set({ user }),
  login: (token, user) => set({ token, user }),  // kept for backward compat
  logout: () => set({ user: null, token: null }),
}))

export default useAuthStore

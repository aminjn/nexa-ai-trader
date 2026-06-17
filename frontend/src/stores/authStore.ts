import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import api from '../lib/api'

interface AuthState {
  token: string | null
  userId: number | null
  isSuperAdmin: boolean
  fullName: string
  email: string | null
  isAuthenticated: boolean
  login: (token: string, userId: number, isSuperAdmin: boolean, fullName: string) => void
  logout: () => void
  setUserInfo: (info: { email?: string; fullName?: string }) => void
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      token: null,
      userId: null,
      isSuperAdmin: false,
      fullName: '',
      email: null,
      isAuthenticated: false,
      login: (token, userId, isSuperAdmin, fullName) => {
        api.defaults.headers.common['Authorization'] = `Bearer ${token}`
        set({ token, userId, isSuperAdmin, fullName, isAuthenticated: true })
      },
      logout: () => {
        delete api.defaults.headers.common['Authorization']
        set({ token: null, userId: null, isSuperAdmin: false, fullName: '', isAuthenticated: false })
      },
      setUserInfo: (info) => set((s) => ({ ...s, ...info })),
    }),
    {
      name: 'nexa-auth',
      onRehydrateStorage: () => (state) => {
        if (state?.token) {
          api.defaults.headers.common['Authorization'] = `Bearer ${state.token}`
        }
      },
    }
  )
)

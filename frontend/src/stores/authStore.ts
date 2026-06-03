// Lightweight client-side auth GATE — NOT real authentication. There is no backend
// auth in this app: the password is never checked, and the "user" is just persisted to
// localStorage so the gate survives reloads. This exists to shape the UX (login → hero
// → console), not to secure anything.
import { create } from 'zustand'

export interface AuthUser {
  name: string
  email: string
  role: string
}

interface AuthState {
  isAuthenticated: boolean
  user: AuthUser | null
  login: (email: string, password: string) => void
  signup: (name: string, email: string, password: string, role: string) => void
  logout: () => void
}

function persist(user: AuthUser | null) {
  if (user) localStorage.setItem('aegis-auth', JSON.stringify(user))
  else localStorage.removeItem('aegis-auth')
}

function readStored(): AuthUser | null {
  try {
    const raw = localStorage.getItem('aegis-auth')
    return raw ? (JSON.parse(raw) as AuthUser) : null
  } catch {
    return null
  }
}

const stored = typeof localStorage !== 'undefined' ? readStored() : null

export const useAuthStore = create<AuthState>((set) => ({
  isAuthenticated: !!stored,
  user: stored,
  login: (email) => {
    const user: AuthUser = { name: email.split('@')[0] || 'Commander', email, role: 'Commander' }
    persist(user)
    set({ isAuthenticated: true, user })
  },
  signup: (name, email, _password, role) => {
    const user: AuthUser = {
      name: name.trim() || email.split('@')[0] || 'Commander',
      email,
      role: role.trim() || 'Commander',
    }
    persist(user)
    set({ isAuthenticated: true, user })
  },
  logout: () => {
    persist(null)
    set({ isAuthenticated: false, user: null })
  },
}))

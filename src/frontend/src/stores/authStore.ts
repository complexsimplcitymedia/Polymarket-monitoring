import { create } from 'zustand'

export interface AuthUser {
    name: string
    email: string
    avatar?: string
    role: string
    provider?: string
}

interface AuthStore {
    isAuthenticated: boolean
    token: string | null
    user: AuthUser | null
    login: (token: string, user?: Partial<AuthUser>) => void
    logout: () => void
}

const STORAGE_KEY = 'csmp_auth_session'

const getStoredSession = (): { token: string | null; user: AuthUser | null } => {
    try {
        const saved = localStorage.getItem(STORAGE_KEY)
        if (saved) {
            const parsed = JSON.parse(saved)
            if (parsed.token) {
                return { token: parsed.token, user: parsed.user || { name: 'Authorized Operator', email: 'operator@complexsimplicity.media', role: 'Admin' } }
            }
        }
    } catch {
        // ignore
    }
    return { token: null, user: null }
}

const initialSession = getStoredSession()

export const useAuthStore = create<AuthStore>((set) => ({
    isAuthenticated: !!initialSession.token,
    token: initialSession.token,
    user: initialSession.user,
    login: (token: string, user?: Partial<AuthUser>) => {
        const authUser: AuthUser = {
            name: user?.name || 'Authorized Operator',
            email: user?.email || 'operator@complexsimplicity.media',
            role: user?.role || 'Principal Trader',
            provider: user?.provider || 'OAuth / Passkey',
            avatar: user?.avatar,
        }
        localStorage.setItem(STORAGE_KEY, JSON.stringify({ token, user: authUser }))
        set({ isAuthenticated: true, token, user: authUser })
    },
    logout: () => {
        localStorage.removeItem(STORAGE_KEY)
        set({ isAuthenticated: false, token: null, user: null })
    },
}))

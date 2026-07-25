/**
 * useAuth — session/auth context for the whole app.
 *
 * AuthProvider resolves the current session on mount (GET /api/auth/me),
 * exposes login/logout, and a 401-aware `authFetch` helper that clears the
 * session (so the route guard in App.jsx redirects to /login) whenever the
 * backend says the session is no longer valid.
 *
 * Response shapes are normalised defensively — /api/auth/me and
 * /api/auth/login both wrap the user as {user: {...}}, but we accept a bare
 * user object too in case that ever changes server-side.
 */
import { createContext, useContext, useState, useEffect, useCallback } from 'react'

const API_BASE = ''

const AuthContext = createContext(null)

function extractUser(data) {
  if (!data) return null
  return data.user ?? data
}

async function parseErrorMessage(res, fallback) {
  try {
    const data = await res.json()
    const detail = data?.detail
    if (typeof detail === 'string') return detail
    if (detail?.message) return detail.message
    return fallback
  } catch {
    return fallback
  }
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const res = await fetch(`${API_BASE}/api/auth/me`)
        if (cancelled) return
        setUser(res.ok ? extractUser(await res.json()) : null)
      } catch {
        if (!cancelled) setUser(null)
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => { cancelled = true }
  }, [])

  const login = useCallback(async (username, password) => {
    let res
    try {
      res = await fetch(`${API_BASE}/api/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
      })
    } catch {
      throw new Error('Unable to reach the server. Please try again.')
    }

    if (!res.ok) {
      if (res.status === 401) throw new Error('Invalid username or password')
      throw new Error(await parseErrorMessage(res, 'Login failed. Please try again.'))
    }

    const loggedInUser = extractUser(await res.json())
    setUser(loggedInUser)
    return loggedInUser
  }, [])

  const logout = useCallback(async () => {
    try {
      await fetch(`${API_BASE}/api/auth/logout`, { method: 'POST' })
    } catch {
      // ignore network errors — we're logging out client-side regardless
    }
    setUser(null)
    window.location.href = '/login'
  }, [])

  /**
   * Fetch wrapper that treats a 401 response as "session expired": clears
   * the user so <RequireAuth> redirects to /login on the next render.
   * Always returns the raw Response — callers still handle ok/error bodies.
   */
  const authFetch = useCallback(async (url, opts) => {
    const res = await fetch(url, opts)
    if (res.status === 401) setUser(null)
    return res
  }, [])

  const value = { user, loading, login, logout, authFetch }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth() must be used within an <AuthProvider>')
  return ctx
}

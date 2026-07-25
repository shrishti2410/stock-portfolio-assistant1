/**
 * Login — standalone full-screen sign-in page (no sidebar/shell).
 */
import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Card, Button } from '../ui'
import { useAuth } from '../shell/useAuth'

export default function Login() {
  const { user, loading, login } = useAuth()
  const navigate = useNavigate()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  // Already signed in (e.g. navigated here manually) — bounce to the app.
  useEffect(() => {
    if (!loading && user) navigate('/', { replace: true })
  }, [user, loading, navigate])

  async function handleSubmit(e) {
    e.preventDefault()
    if (submitting || !username || !password) return
    setError('')
    setSubmitting(true)
    try {
      await login(username, password)
      navigate('/', { replace: true })
    } catch (err) {
      setError(err.message || 'Invalid username or password')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-app px-4">
      <div className="w-full max-w-sm">
        {/* Brand */}
        <div className="flex flex-col items-center mb-8">
          <div className="w-12 h-12 rounded-xl bg-brand flex items-center justify-center mb-3">
            <span className="text-white font-bold text-lg">TD</span>
          </div>
          <h1 className="text-lg font-bold text-ink">Trading Desk</h1>
          <p className="text-xs text-ink-muted mt-1">Sign in to your workspace</p>
        </div>

        <Card>
          <form onSubmit={handleSubmit} className="space-y-4">
            {error && (
              <div className="bg-red-500/10 border border-red-500/30 rounded-lg px-3 py-2.5 text-xs text-red-500 dark:text-red-400">
                {error}
              </div>
            )}
            <div>
              <label htmlFor="login-username" className="block text-[11px] font-medium text-ink-muted mb-1">
                Username
              </label>
              <input
                id="login-username"
                type="text"
                autoFocus
                autoComplete="username"
                value={username}
                onChange={e => setUsername(e.target.value)}
                placeholder="you"
                className="w-full px-3 py-2 bg-surface-2 border border-edge rounded-lg text-sm text-ink
                           placeholder:text-ink-subtle focus:outline-none focus:border-brand/50 transition-colors"
              />
            </div>
            <div>
              <label htmlFor="login-password" className="block text-[11px] font-medium text-ink-muted mb-1">
                Password
              </label>
              <input
                id="login-password"
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                placeholder="••••••••"
                className="w-full px-3 py-2 bg-surface-2 border border-edge rounded-lg text-sm text-ink
                           placeholder:text-ink-subtle focus:outline-none focus:border-brand/50 transition-colors"
              />
            </div>
            <Button type="submit" className="w-full justify-center" loading={submitting} disabled={!username || !password}>
              Sign in
            </Button>
          </form>
        </Card>

        <p className="text-center text-[11px] text-ink-subtle mt-6">Trading Desk · India + US markets</p>
      </div>
    </div>
  )
}

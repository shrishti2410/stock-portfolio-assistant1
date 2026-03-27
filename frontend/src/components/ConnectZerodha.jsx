/**
 * ConnectZerodha — one-click Zerodha OAuth connection panel.
 *
 * State is persisted in localStorage ('zerodha_connected').
 * On mount, if localStorage already says connected, the panel shows
 * the connected state immediately — no re-login needed.
 *
 * Flow for first-time connection:
 *   1. "Connect Zerodha Account" → GET /api/auth/login → open tab
 *   2. Zerodha redirects to backend /api/auth/callback → token saved
 *   3. "I've logged in — check now" → GET /api/auth/status
 *      connected: true  → persist to localStorage, show success, call onSuccess()
 *      connected: false → amber nudge to finish login
 *
 * Props:
 *   onSuccess    () => void   Called when connection is confirmed
 *   onClose      () => void   Called when user dismisses the panel
 *   onDisconnect () => void   Called after successful disconnect
 */

import { useEffect, useState } from 'react'

const API_BASE        = 'http://localhost:8000'
const STORAGE_KEY     = 'zerodha_connected'

function isStoredConnected() {
  return localStorage.getItem(STORAGE_KEY) === 'true'
}

export default function ConnectZerodha({ onSuccess, onClose, onDisconnect }) {
  // Initialise directly from localStorage so state survives re-renders / revisits
  const [step,     setStep]     = useState(() => isStoredConnected() ? 'connected' : 'idle')
  const [errorMsg, setErrorMsg] = useState('')

  // Keep step in sync if localStorage was set by another tab / earlier session
  useEffect(() => {
    if (isStoredConnected() && step !== 'connected') {
      setStep('connected')
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // ── Step 1: open Zerodha login tab ────────────────────────────────────────
  async function handleConnect() {
    setStep('opening')
    setErrorMsg('')
    try {
      const res = await fetch(`${API_BASE}/api/auth/login`)
      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        throw new Error(body.detail ?? `Server error ${res.status}`)
      }
      const { login_url } = await res.json()
      window.open(login_url, '_blank', 'noopener,noreferrer')
      setStep('waiting')
    } catch (err) {
      setErrorMsg(err.message ?? 'Failed to get login URL')
      setStep('error')
    }
  }

  // ── Step 2: check if backend saved the token ──────────────────────────────
  async function handleCheck() {
    setStep('checking')
    setErrorMsg('')
    try {
      const res = await fetch(`${API_BASE}/api/auth/status`)
      if (!res.ok) throw new Error(`Server error ${res.status}`)
      const { connected } = await res.json()
      if (connected) {
        localStorage.setItem(STORAGE_KEY, 'true')
        setStep('connected')
        setTimeout(() => onSuccess(), 1500)
      } else {
        setStep('not_connected')
      }
    } catch (err) {
      setErrorMsg(err.message ?? 'Could not verify connection status')
      setStep('error')
    }
  }

  // ── Disconnect ────────────────────────────────────────────────────────────
  async function handleDisconnect() {
    try {
      await fetch(`${API_BASE}/api/auth/logout`, { method: 'DELETE' })
    } catch { /* best-effort */ }
    localStorage.removeItem(STORAGE_KEY)
    setStep('idle')
    setErrorMsg('')
    onDisconnect?.()
  }

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <div className="border-b border-slate-700 bg-slate-900/60 backdrop-blur">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 py-5">
        <div className="bg-slate-800/80 border border-slate-700 rounded-xl p-6 max-w-lg">

          {/* Header */}
          <div className="flex items-center justify-between mb-5">
            <div>
              <h2 className="text-base font-bold text-white tracking-tight">
                Connect Zerodha Account
              </h2>
              <p className="text-xs text-slate-500 mt-0.5">
                Link your Kite account to load live positions
              </p>
            </div>
            <button
              onClick={onClose}
              className="text-slate-500 hover:text-slate-300 text-lg leading-none transition-colors"
              aria-label="Close"
            >
              ✕
            </button>
          </div>

          {/* ── Connected ── */}
          {step === 'connected' && (
            <div className="space-y-3">
              <div className="flex items-center gap-3 bg-emerald-500/10 border border-emerald-500/30
                              rounded-lg px-4 py-3 text-emerald-300 text-sm font-medium">
                <span>✓</span>
                Connected to Zerodha! Showing available data.
              </div>
              <button
                onClick={handleDisconnect}
                className="w-full px-4 py-2 bg-slate-700 hover:bg-slate-600 border border-slate-600
                           rounded-lg text-slate-300 text-sm transition-colors"
              >
                Disconnect
              </button>
            </div>
          )}

          {/* ── Not connected yet nudge ── */}
          {step === 'not_connected' && (
            <div className="mb-4 bg-amber-500/10 border border-amber-500/30 rounded-lg px-4 py-3
                            text-amber-300 text-sm">
              Token not saved yet — finish the login on the Zerodha tab, then check again.
            </div>
          )}

          {/* ── Error ── */}
          {step === 'error' && (
            <div className="mb-4 bg-red-500/10 border border-red-500/30 rounded-lg px-4 py-3
                            text-red-400 text-sm">
              {errorMsg}
            </div>
          )}

          {step !== 'connected' && (
            <div className="flex flex-col gap-3">

              {/* Connect / re-open button */}
              <button
                onClick={handleConnect}
                disabled={step === 'opening' || step === 'checking'}
                className="w-full flex items-center justify-center gap-2 px-4 py-2.5
                           bg-blue-600 hover:bg-blue-500 disabled:opacity-50
                           disabled:cursor-not-allowed rounded-lg text-white text-sm
                           font-semibold transition-colors"
              >
                {step === 'opening' ? (
                  <><span className="animate-spin">↻</span> Opening Zerodha…</>
                ) : (
                  <><span>⚡</span>
                    {step === 'waiting' || step === 'not_connected' || step === 'error'
                      ? 'Re-open Zerodha Login'
                      : 'Connect Zerodha Account'}
                  </>
                )}
              </button>

              {/* Check-status panel — visible after login tab was opened */}
              {(step === 'waiting' || step === 'not_connected' || step === 'checking') && (
                <div className="border border-slate-700 rounded-lg p-4 flex flex-col gap-3
                                bg-slate-700/20">
                  <p className="text-xs text-slate-400 leading-relaxed">
                    A Zerodha login page has opened in a new tab. After you log in,
                    Zerodha redirects to the backend automatically and saves your token.
                    Come back here and click the button below.
                  </p>
                  <button
                    onClick={handleCheck}
                    disabled={step === 'checking'}
                    className="w-full flex items-center justify-center gap-2 px-4 py-2.5
                               bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50
                               disabled:cursor-not-allowed rounded-lg text-white text-sm
                               font-semibold transition-colors"
                  >
                    {step === 'checking'
                      ? <><span className="animate-spin">↻</span> Checking…</>
                      : "I've logged in — check now"
                    }
                  </button>
                </div>
              )}

            </div>
          )}

        </div>
      </div>
    </div>
  )
}

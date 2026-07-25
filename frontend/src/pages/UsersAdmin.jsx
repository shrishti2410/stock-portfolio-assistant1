/**
 * UsersAdmin — manage logins for this deployment ("/settings/users").
 * Admin-only (gated on user.is_admin); also hosts a generic "change my
 * password" card since /api/auth/password works for any authenticated user.
 */
import { useState, useEffect, useCallback } from 'react'
import { PageHeader, Card, CardHeader, Button, StatusBadge, DataTable, LoadingSpinner, EmptyState } from '../ui'
import { IconUsers, IconEye, IconEyeOff } from '../ui/icons'
import { useAuth } from '../shell/useAuth'

const API_BASE = ''

function fmtDate(iso) {
  if (!iso) return '—'
  const d = new Date(iso.includes('T') ? iso : iso.replace(' ', 'T') + 'Z')
  if (Number.isNaN(d.getTime())) return String(iso).slice(0, 10)
  return d.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' })
}

function PasswordField({ label, value, onChange, placeholder, autoComplete }) {
  const [show, setShow] = useState(false)
  return (
    <div>
      <label className="block text-[11px] font-medium text-ink-muted mb-1">{label}</label>
      <div className="relative">
        <input
          type={show ? 'text' : 'password'}
          value={value}
          onChange={e => onChange(e.target.value)}
          placeholder={placeholder}
          autoComplete={autoComplete || 'off'}
          spellCheck={false}
          className="w-full px-3 py-2 pr-9 bg-surface-2 border border-edge rounded-lg text-sm text-ink
                     placeholder:text-ink-subtle focus:outline-none focus:border-brand/50 transition-colors"
        />
        <button
          type="button"
          onClick={() => setShow(s => !s)}
          tabIndex={-1}
          className="absolute right-2 top-1/2 -translate-y-1/2 p-1 rounded text-ink-subtle hover:text-ink transition-colors"
          aria-label={show ? `Hide ${label}` : `Show ${label}`}
        >
          {show ? <IconEyeOff className="w-4 h-4" /> : <IconEye className="w-4 h-4" />}
        </button>
      </div>
    </div>
  )
}

function TextField({ label, value, onChange, placeholder }) {
  return (
    <div>
      <label className="block text-[11px] font-medium text-ink-muted mb-1">{label}</label>
      <input
        type="text"
        value={value}
        onChange={e => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full px-3 py-2 bg-surface-2 border border-edge rounded-lg text-sm text-ink
                   placeholder:text-ink-subtle focus:outline-none focus:border-brand/50 transition-colors"
      />
    </div>
  )
}

function AddUserCard({ authFetch, onAdded }) {
  const [form, setForm] = useState({ username: '', display_name: '', password: '', is_admin: false })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  function setField(k, v) { setForm(f => ({ ...f, [k]: v })) }

  async function submit(e) {
    e.preventDefault()
    if (!form.username.trim() || !form.password) return
    setSaving(true); setError('')
    try {
      const res = await authFetch(`${API_BASE}/api/auth/users`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          username: form.username.trim(),
          display_name: form.display_name.trim() || undefined,
          password: form.password,
          is_admin: form.is_admin,
        }),
      })
      if (res.ok) {
        setForm({ username: '', display_name: '', password: '', is_admin: false })
        onAdded()
      } else {
        const data = await res.json().catch(() => null)
        setError(data?.detail?.message || data?.detail || 'Failed to create user')
      }
    } catch {
      setError('Network error — please try again')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Card>
      <CardHeader title="Add user" subtitle="Create a new login for this deployment" />
      <form onSubmit={submit} className="space-y-3">
        {error && (
          <div className="bg-red-500/10 border border-red-500/30 rounded-lg px-3 py-2 text-xs text-red-500 dark:text-red-400">
            {error}
          </div>
        )}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <TextField label="Username" value={form.username} onChange={v => setField('username', v)} placeholder="jdoe" />
          <TextField label="Display name" value={form.display_name} onChange={v => setField('display_name', v)} placeholder="Jane Doe" />
          <PasswordField label="Password" value={form.password} onChange={v => setField('password', v)} placeholder="••••••••" autoComplete="new-password" />
          <label className="flex items-center gap-2 text-xs text-ink-muted cursor-pointer self-end pb-2.5">
            <input type="checkbox" checked={form.is_admin} onChange={e => setField('is_admin', e.target.checked)} />
            Admin access
          </label>
        </div>
        <Button type="submit" loading={saving} disabled={!form.username.trim() || !form.password}>Add user</Button>
      </form>
    </Card>
  )
}

function ChangePasswordCard({ authFetch }) {
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [saving, setSaving] = useState(false)
  const [msg, setMsg] = useState(null)

  async function submit(e) {
    e.preventDefault()
    if (!current || !next) return
    setSaving(true); setMsg(null)
    try {
      const res = await authFetch(`${API_BASE}/api/auth/password`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ current_password: current, new_password: next }),
      })
      if (res.ok) {
        setMsg({ ok: true, text: 'Password updated' })
        setCurrent(''); setNext('')
      } else {
        const data = await res.json().catch(() => null)
        setMsg({ ok: false, text: data?.detail?.message || data?.detail || 'Failed to update password' })
      }
    } catch {
      setMsg({ ok: false, text: 'Network error — please try again' })
    } finally {
      setSaving(false)
    }
  }

  return (
    <Card>
      <CardHeader title="Change my password" subtitle="Applies to your own login" />
      <form onSubmit={submit} className="space-y-3">
        {msg && (
          <div className={`rounded-lg px-3 py-2 text-xs border ${msg.ok
            ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-600 dark:text-emerald-300'
            : 'bg-red-500/10 border-red-500/30 text-red-500 dark:text-red-400'}`}
          >
            {msg.text}
          </div>
        )}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <PasswordField label="Current password" value={current} onChange={setCurrent} placeholder="••••••••" autoComplete="current-password" />
          <PasswordField label="New password" value={next} onChange={setNext} placeholder="••••••••" autoComplete="new-password" />
        </div>
        <Button type="submit" loading={saving} disabled={!current || !next}>Update password</Button>
      </form>
    </Card>
  )
}

export default function UsersAdmin() {
  const { user, authFetch } = useAuth()
  const [users, setUsers] = useState([])
  const [loading, setLoading] = useState(true)
  const [deletingId, setDeletingId] = useState(null)
  const [deleteError, setDeleteError] = useState('')

  const loadUsers = useCallback(async () => {
    setLoading(true)
    try {
      const res = await authFetch(`${API_BASE}/api/auth/users`)
      setUsers(res.ok ? await res.json() : [])
    } catch {
      setUsers([])
    } finally {
      setLoading(false)
    }
  }, [authFetch])

  useEffect(() => {
    if (user?.is_admin) loadUsers()
    else setLoading(false)
  }, [user, loadUsers])

  async function handleDelete(row) {
    if (row.id === user.id) return
    if (!window.confirm(`Delete user "${row.username}"? This cannot be undone.`)) return
    setDeletingId(row.id); setDeleteError('')
    try {
      const res = await authFetch(`${API_BASE}/api/auth/users/${row.id}`, { method: 'DELETE' })
      if (res.ok) {
        await loadUsers()
      } else {
        const data = await res.json().catch(() => null)
        setDeleteError(data?.detail?.message || data?.detail || 'Failed to delete user')
      }
    } catch {
      setDeleteError('Network error — please try again')
    } finally {
      setDeletingId(null)
    }
  }

  if (!user?.is_admin) {
    return (
      <div className="max-w-5xl mx-auto px-4 sm:px-6 py-6">
        <PageHeader
          title="Users"
          icon={IconUsers}
          breadcrumb={[{ label: 'Settings', to: '/settings' }, { label: 'Users' }]}
        />
        <EmptyState
          icon={IconUsers}
          title="Admins only"
          description="You need administrator access to manage users on this deployment."
        />
      </div>
    )
  }

  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 py-6">
      <PageHeader
        title="Users"
        subtitle="Manage logins for this deployment"
        icon={IconUsers}
        breadcrumb={[{ label: 'Settings', to: '/settings' }, { label: 'Users' }]}
      />

      <div className="mb-5">
        <Card padding="p-0">
          <div className="px-5 pt-4 pb-2 flex items-center justify-between">
            <h3 className="text-sm font-semibold text-ink">All users</h3>
          </div>
          {deleteError && (
            <div className="mx-5 mb-3 bg-red-500/10 border border-red-500/30 rounded-lg px-3 py-2 text-xs text-red-500 dark:text-red-400">
              {deleteError}
            </div>
          )}
          {loading ? (
            <LoadingSpinner message="Loading users…" />
          ) : (
            <DataTable
              columns={[
                { key: 'username', header: 'Username' },
                { key: 'display_name', header: 'Display Name', render: r => r.display_name || '—' },
                {
                  key: 'is_admin', header: 'Role', align: 'center', render: r => (
                    <StatusBadge label={r.is_admin ? 'Admin' : 'User'} tone={r.is_admin ? 'brand' : 'neutral'} dot={false} />
                  ),
                },
                { key: 'created_at', header: 'Created', render: r => fmtDate(r.created_at) },
                {
                  key: 'actions', header: '', align: 'right', sortable: false, render: r => (
                    <Button
                      variant="danger" size="sm"
                      loading={deletingId === r.id}
                      disabled={r.id === user.id}
                      title={r.id === user.id ? "You can't delete your own account" : 'Delete user'}
                      onClick={() => handleDelete(r)}
                    >
                      Delete
                    </Button>
                  ),
                },
              ]}
              rows={users}
              searchKeys={['username', 'display_name']}
              emptyMessage="No users yet."
            />
          )}
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <AddUserCard authFetch={authFetch} onAdded={loadUsers} />
        <ChangePasswordCard authFetch={authFetch} />
      </div>
    </div>
  )
}

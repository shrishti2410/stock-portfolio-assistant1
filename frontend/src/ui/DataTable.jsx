/**
 * DataTable — in-table search + sort + pagination (DQH style).
 *
 * columns: [{ key, header, align?, sortable?, render?(row), className? }]
 * rows:    array of objects
 * Props: searchable, searchKeys, pageSize, onRowClick, emptyMessage, dense
 */
import { useState, useMemo } from 'react'

function SortIcon({ dir }) {
  return (
    <span className="inline-flex flex-col ml-1 -space-y-1 align-middle">
      <span className={dir === 'asc' ? 'text-brand' : 'text-ink-subtle/40'}>▲</span>
      <span className={dir === 'desc' ? 'text-brand' : 'text-ink-subtle/40'} style={{ fontSize: '0.6em' }}>▼</span>
    </span>
  )
}

export function DataTable({
  columns, rows, searchable = true, searchKeys, pageSize = 20,
  onRowClick, emptyMessage = 'No records.', dense = false, className = '',
  toolbar,
}) {
  const [query, setQuery] = useState('')
  const [sortKey, setSortKey] = useState(null)
  const [sortDir, setSortDir] = useState('asc')
  const [page, setPage] = useState(0)

  const keys = searchKeys ?? columns.map(c => c.key)

  const filtered = useMemo(() => {
    let out = rows ?? []
    if (query.trim()) {
      const q = query.toLowerCase()
      out = out.filter(r => keys.some(k => String(r[k] ?? '').toLowerCase().includes(q)))
    }
    if (sortKey) {
      out = [...out].sort((a, b) => {
        const av = a[sortKey], bv = b[sortKey]
        if (av === bv) return 0
        if (av === undefined || av === null) return 1
        if (bv === undefined || bv === null) return -1
        const cmp = typeof av === 'number' && typeof bv === 'number'
          ? av - bv
          : String(av).localeCompare(String(bv))
        return sortDir === 'asc' ? cmp : -cmp
      })
    }
    return out
  }, [rows, query, sortKey, sortDir, keys])

  const pageCount = Math.max(1, Math.ceil(filtered.length / pageSize))
  const safePage = Math.min(page, pageCount - 1)
  const pageRows = filtered.slice(safePage * pageSize, safePage * pageSize + pageSize)

  function toggleSort(key) {
    if (sortKey === key) {
      setSortDir(d => (d === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortKey(key); setSortDir('asc')
    }
  }

  const cellPad = dense ? 'px-3 py-1.5' : 'px-4 py-2.5'

  return (
    <div className={`bg-surface border border-edge rounded-xl overflow-hidden ${className}`}>
      {(searchable || toolbar) && (
        <div className="flex items-center justify-between gap-3 px-4 py-3 border-b border-edge">
          {searchable ? (
            <div className="relative flex-1 max-w-xs">
              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-subtle text-sm pointer-events-none">⌕</span>
              <input
                value={query}
                onChange={e => { setQuery(e.target.value); setPage(0) }}
                placeholder="Search…"
                className="w-full pl-8 pr-3 py-1.5 bg-surface-2 border border-edge rounded-lg text-sm text-ink
                           placeholder:text-ink-subtle focus:outline-none focus:border-brand/50 transition-colors"
              />
            </div>
          ) : <div />}
          {toolbar}
        </div>
      )}

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-[10px] uppercase tracking-wide text-ink-subtle bg-surface-2 border-b border-edge">
              {columns.map(col => (
                <th
                  key={col.key}
                  className={`${cellPad} font-semibold whitespace-nowrap
                    ${col.align === 'right' ? 'text-right' : col.align === 'center' ? 'text-center' : 'text-left'}
                    ${col.sortable !== false ? 'cursor-pointer select-none hover:text-ink' : ''}`}
                  onClick={col.sortable !== false ? () => toggleSort(col.key) : undefined}
                >
                  {col.header}
                  {col.sortable !== false && <SortIcon dir={sortKey === col.key ? sortDir : null} />}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {pageRows.length === 0 ? (
              <tr><td colSpan={columns.length} className="px-4 py-10 text-center text-ink-muted text-sm">{emptyMessage}</td></tr>
            ) : pageRows.map((row, i) => (
              <tr
                key={row.id ?? row.symbol ?? i}
                onClick={onRowClick ? () => onRowClick(row) : undefined}
                className={`border-b border-edge/60 last:border-0 transition-colors
                  ${onRowClick ? 'cursor-pointer hover:bg-surface-2' : 'hover:bg-surface-2/60'}`}
              >
                {columns.map(col => (
                  <td
                    key={col.key}
                    className={`${cellPad} text-ink
                      ${col.align === 'right' ? 'text-right tnum' : col.align === 'center' ? 'text-center' : 'text-left'}
                      ${col.className ?? ''}`}
                  >
                    {col.render ? col.render(row) : (row[col.key] ?? '—')}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {filtered.length > pageSize && (
        <div className="flex items-center justify-between px-4 py-2.5 border-t border-edge text-xs text-ink-muted">
          <span className="tnum">
            {safePage * pageSize + 1}–{Math.min((safePage + 1) * pageSize, filtered.length)} of {filtered.length}
          </span>
          <div className="flex items-center gap-1">
            <button
              onClick={() => setPage(p => Math.max(0, p - 1))}
              disabled={safePage === 0}
              className="px-2.5 py-1 rounded-md border border-edge hover:bg-surface-2 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >Prev</button>
            <span className="px-2 tnum">{safePage + 1} / {pageCount}</span>
            <button
              onClick={() => setPage(p => Math.min(pageCount - 1, p + 1))}
              disabled={safePage >= pageCount - 1}
              className="px-2.5 py-1 rounded-md border border-edge hover:bg-surface-2 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >Next</button>
          </div>
        </div>
      )}
    </div>
  )
}

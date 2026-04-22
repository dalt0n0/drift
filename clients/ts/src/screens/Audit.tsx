import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Ic } from '../components/Icon'
import { Card, EmptyState, Input, Spinner, Tag } from '../components/primitives'
import { getAudit } from '../api'
import type { AuditEntry, Engagement } from '../types'

interface Props { engagement: Engagement | null }

const ACTION_COLORS: Record<string, string> = {
  create: '#34d399',
  update: '#4ea8ff',
  delete: '#ff4a5e',
  login: '#c084fc',
  logout: '#7a828f',
  export: '#ffaa00',
  reveal: '#ff8847',
  launch: '#34d399',
}

const ACTION_ICONS: Record<string, string> = {
  create: 'plus',
  update: 'edit',
  delete: 'trash',
  login: 'key',
  logout: 'key',
  export: 'download',
  reveal: 'eye',
  launch: 'play',
}

function AuditRow({ entry }: { entry: AuditEntry }) {
  const verb = entry.action?.split('_')[0] || 'action'
  const color = ACTION_COLORS[verb] || 'var(--text-3)'
  const icon = ACTION_ICONS[verb] || 'shield'

  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: '160px 90px 140px 1fr',
      gap: 14, alignItems: 'center',
      padding: '10px 16px',
      borderBottom: '1px solid var(--line)',
      fontSize: 12.5,
    }} className="hover-row">
      <div style={{ fontFamily: 'var(--mono)', fontSize: 11.5, color: 'var(--text-3)' }}>
        {new Date(entry.timestamp).toLocaleString()}
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
        <div style={{ width: 20, height: 20, borderRadius: 5, background: `${color}18`, color, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <Ic name={icon} size={11} />
        </div>
        <span style={{ fontSize: 11.5, fontFamily: 'var(--mono)', color }}>{verb}</span>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
        <div style={{ width: 22, height: 22, borderRadius: 999, background: 'var(--accent-bg)', color: 'var(--accent)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 10, fontFamily: 'var(--mono)', fontWeight: 600, border: '1px solid var(--accent-line)', flexShrink: 0 }}>
          {(entry.actor_id || 'sys').slice(0, 2).toUpperCase()}
        </div>
        <span style={{ color: 'var(--text-2)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {entry.actor_id || 'system'}
        </span>
      </div>
      <div style={{ color: 'var(--text-2)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
        <span style={{ fontFamily: 'var(--mono)', fontSize: 11.5, color: 'var(--text-3)', marginRight: 6 }}>
          {entry.resource_type}
        </span>
        {entry.action}
        {entry.detail && (
          <span style={{ color: 'var(--text-3)', fontSize: 11.5, marginLeft: 6 }}>
            {JSON.stringify(entry.detail)}
          </span>
        )}
      </div>
    </div>
  )
}

const VERBS = ['all', 'create', 'update', 'delete', 'login', 'export', 'reveal', 'launch']
const RESOURCE_TYPES = ['all', 'engagement', 'finding', 'scope', 'run', 'credential', 'report', 'user']

export default function Audit({ engagement }: Props) {
  const [search, setSearch] = useState('')
  const [verbFilter, setVerbFilter] = useState('all')
  const [resourceFilter, setResourceFilter] = useState('all')
  const [page, setPage] = useState(0)
  const PAGE_SIZE = 50

  const { data: entries = [], isLoading } = useQuery({
    queryKey: ['audit', engagement?.id],
    queryFn: () => getAudit(),
    staleTime: 10_000,
  })

  if (!engagement) return <EmptyState icon="shield" title="No engagement selected" />

  const filtered = entries.filter(e => {
    const verb = e.action?.split('_')[0] || ''
    const matchVerb = verbFilter === 'all' || verb === verbFilter
    const matchResource = resourceFilter === 'all' || e.resource_type === resourceFilter
    const detailStr = e.detail ? JSON.stringify(e.detail) : ''
    const matchSearch = !search || e.action?.includes(search) || e.actor_id?.includes(search) || detailStr.includes(search)
    return matchVerb && matchResource && matchSearch
  })

  const paged = filtered.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE)
  const totalPages = Math.ceil(filtered.length / PAGE_SIZE)

  return (
    <div style={{ padding: '18px 24px', height: 'calc(100vh - 46px)', overflow: 'auto' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
        <div>
          <div style={{ fontSize: 18, fontWeight: 600, letterSpacing: '-0.02em' }}>Audit log</div>
          <div style={{ fontSize: 12, color: 'var(--text-3)', marginTop: 2, fontFamily: 'var(--mono)' }}>
            {filtered.length} events · tamper-evident append-only
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <div style={{ width: 7, height: 7, borderRadius: 999, background: 'var(--ok)' }} />
          <span style={{ fontSize: 11.5, color: 'var(--text-3)' }}>Live</span>
        </div>
      </div>

      {/* Filters */}
      <Card style={{ marginBottom: 12, padding: '10px 14px' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, height: 30, background: 'var(--bg-2)', border: '1px solid var(--line)', borderRadius: 6, padding: '0 10px', marginBottom: 2 }}>
            <Ic name="search" size={13} style={{ color: 'var(--text-3)' }} />
            <input
              value={search}
              onChange={e => { setSearch(e.target.value); setPage(0) }}
              placeholder="Search actions, actors, details…"
              style={{ flex: 1, fontSize: 12.5, background: 'none', color: 'var(--text)' }}
            />
          </div>
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
            <div>
              <div style={{ fontSize: 10.5, color: 'var(--text-4)', marginBottom: 4, textTransform: 'uppercase', letterSpacing: '0.06em' }}>Action</div>
              <div style={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
                {VERBS.map(v => (
                  <button key={v} onClick={() => { setVerbFilter(v); setPage(0) }} style={{
                    padding: '2px 8px', borderRadius: 4, fontSize: 11, textTransform: 'capitalize',
                    background: verbFilter === v ? 'var(--bg-3)' : 'transparent',
                    color: verbFilter === v ? 'var(--text)' : 'var(--text-3)',
                  }}>{v}</button>
                ))}
              </div>
            </div>
            <div style={{ width: 1, background: 'var(--line)' }} />
            <div>
              <div style={{ fontSize: 10.5, color: 'var(--text-4)', marginBottom: 4, textTransform: 'uppercase', letterSpacing: '0.06em' }}>Resource</div>
              <div style={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
                {RESOURCE_TYPES.map(r => (
                  <button key={r} onClick={() => { setResourceFilter(r); setPage(0) }} style={{
                    padding: '2px 8px', borderRadius: 4, fontSize: 11, textTransform: 'capitalize',
                    background: resourceFilter === r ? 'var(--bg-3)' : 'transparent',
                    color: resourceFilter === r ? 'var(--text)' : 'var(--text-3)',
                  }}>{r}</button>
                ))}
              </div>
            </div>
          </div>
        </div>
      </Card>

      {/* Table */}
      <Card padding={0}>
        <div style={{ display: 'grid', gridTemplateColumns: '160px 90px 140px 1fr', gap: 14, padding: '7px 16px', borderBottom: '1px solid var(--line)', fontSize: 10.5, color: 'var(--text-3)', textTransform: 'uppercase', letterSpacing: '0.07em' }}>
          <span>Timestamp</span><span>Action</span><span>Actor</span><span>Detail</span>
        </div>

        {isLoading ? (
          <div style={{ display: 'flex', justifyContent: 'center', padding: 48 }}><Spinner /></div>
        ) : paged.length === 0 ? (
          <EmptyState icon="shield" title="No audit events" body="Actions taken within this engagement are logged here." />
        ) : (
          paged.map(e => <AuditRow key={e.id} entry={e} />)
        )}
      </Card>

      {/* Pagination */}
      {totalPages > 1 && (
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: 12, padding: '0 4px', fontSize: 12 }}>
          <span style={{ color: 'var(--text-3)' }}>
            Page {page + 1} of {totalPages} · {filtered.length} events
          </span>
          <div style={{ display: 'flex', gap: 4 }}>
            <button
              disabled={page === 0}
              onClick={() => setPage(p => p - 1)}
              style={{ padding: '4px 10px', borderRadius: 5, fontSize: 12, background: 'var(--bg-2)', border: '1px solid var(--line)', color: page === 0 ? 'var(--text-4)' : 'var(--text-2)', cursor: page === 0 ? 'default' : 'pointer' }}>
              ← Prev
            </button>
            <button
              disabled={page >= totalPages - 1}
              onClick={() => setPage(p => p + 1)}
              style={{ padding: '4px 10px', borderRadius: 5, fontSize: 12, background: 'var(--bg-2)', border: '1px solid var(--line)', color: page >= totalPages - 1 ? 'var(--text-4)' : 'var(--text-2)', cursor: page >= totalPages - 1 ? 'default' : 'pointer' }}>
              Next →
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

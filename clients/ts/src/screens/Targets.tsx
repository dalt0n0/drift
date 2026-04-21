import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Ic } from '../components/Icon'
import { Button, Card, EmptyState, FieldRow, IconButton, Input, Modal, Select, Spinner, Tag } from '../components/primitives'
import { getScope, addScopeItem, deleteScopeItem } from '../api'
import type { Engagement, ScopeItem, ScopeType } from '../types'

interface Props { engagement: Engagement | null }

const SCOPE_TYPES: ScopeType[] = ['host', 'ip', 'cidr', 'url', 'wildcard']

const typeColors: Record<ScopeType, string> = {
  host: '#4ea8ff', ip: '#34d399', cidr: '#c084fc', url: '#ffaa00', wildcard: '#ff8847',
}

function AddScopeModal({ open, onClose, engagementId }: { open: boolean; onClose: () => void; engagementId: string }) {
  const qc = useQueryClient()
  const [type, setType] = useState<ScopeType>('host')
  const [value, setValue] = useState('')
  const [notes, setNotes] = useState('')

  const add = useMutation({
    mutationFn: () => addScopeItem(engagementId, { type, value, notes }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['scope', engagementId] }); setValue(''); setNotes(''); onClose() },
  })

  return (
    <Modal open={open} onClose={onClose} title="Add scope item" width={460}>
      <div style={{ padding: 20, display: 'flex', flexDirection: 'column', gap: 14 }}>
        <FieldRow label="Type">
          <Select value={type} onChange={v => setType(v as ScopeType)}>
            {SCOPE_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
          </Select>
        </FieldRow>
        <FieldRow label="Value *">
          <Input value={value} onChange={setValue} placeholder={
            type === 'host' ? 'api.example.com' :
            type === 'ip' ? '192.168.1.1' :
            type === 'cidr' ? '10.0.0.0/24' :
            type === 'url' ? 'https://example.com/api/*' :
            '*.example.com'
          } />
        </FieldRow>
        <FieldRow label="Notes">
          <Input value={notes} onChange={setNotes} placeholder="Optional notes…" />
        </FieldRow>
        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button variant="primary" onClick={() => add.mutate()} disabled={!value || add.isPending}>
            {add.isPending ? 'Adding…' : 'Add to scope'}
          </Button>
        </div>
      </div>
    </Modal>
  )
}

export default function Targets({ engagement }: Props) {
  const qc = useQueryClient()
  const [view, setView] = useState<'table' | 'grid'>('table')
  const [addOpen, setAddOpen] = useState(false)
  const [search, setSearch] = useState('')
  const [typeFilter, setTypeFilter] = useState('all')

  const { data: scope = [], isLoading } = useQuery({
    queryKey: ['scope', engagement?.id],
    queryFn: () => getScope(engagement!.id),
    enabled: !!engagement?.id,
  })

  const remove = useMutation({
    mutationFn: (id: string) => deleteScopeItem(engagement!.id, id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['scope', engagement!.id] }),
  })

  if (!engagement) return <EmptyState icon="target" title="No engagement selected" />

  const filtered = scope.filter(s =>
    (!search || s.value.toLowerCase().includes(search.toLowerCase()) || s.notes?.toLowerCase().includes(search.toLowerCase())) &&
    (typeFilter === 'all' || s.type === typeFilter)
  )

  const typeCounts: Record<string, number> = {}
  for (const s of scope) typeCounts[s.type] = (typeCounts[s.type] || 0) + 1

  return (
    <div style={{ padding: '18px 24px' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
        <div>
          <div style={{ fontSize: 18, fontWeight: 600, letterSpacing: '-0.02em' }}>Targets & Scope</div>
          <div style={{ fontSize: 12, color: 'var(--text-3)', marginTop: 2 }}>
            {scope.length} items · {new Set(scope.map(s => s.type)).size} types
          </div>
        </div>
        <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
          <div style={{ display: 'flex', background: 'var(--bg-2)', borderRadius: 6, padding: 2, border: '1px solid var(--line)' }}>
            {(['table', 'grid'] as const).map(v => (
              <button key={v} onClick={() => setView(v)} style={{
                padding: '4px 9px', fontSize: 11.5, borderRadius: 4,
                background: view === v ? 'var(--bg-3)' : 'transparent',
                color: view === v ? 'var(--text)' : 'var(--text-3)',
                textTransform: 'capitalize',
              }}>{v}</button>
            ))}
          </div>
          <Button variant="primary" size="md" icon={<Ic name="plus" size={14} />} onClick={() => setAddOpen(true)}>
            Add target
          </Button>
        </div>
      </div>

      {/* Scope editor / stats */}
      <Card style={{ marginBottom: 14 }}>
        <div style={{ fontSize: 13, fontWeight: 500, marginBottom: 12 }}>Scope overview</div>
        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
          {SCOPE_TYPES.map(t => (
            <button key={t} onClick={() => setTypeFilter(typeFilter === t ? 'all' : t)} style={{
              padding: '6px 14px', borderRadius: 8,
              background: typeFilter === t ? `${typeColors[t]}18` : 'var(--bg-2)',
              border: `1px solid ${typeFilter === t ? typeColors[t] + '44' : 'var(--line)'}`,
              color: typeFilter === t ? typeColors[t] : 'var(--text-2)',
              fontSize: 12.5, display: 'flex', alignItems: 'center', gap: 7,
            }}>
              <span style={{ width: 7, height: 7, borderRadius: 999, background: typeColors[t] }} />
              {t} <span style={{ fontFamily: 'var(--mono)', fontSize: 11 }}>{typeCounts[t] || 0}</span>
            </button>
          ))}
        </div>
      </Card>

      {/* Search */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '6px 10px', height: 34, background: 'var(--bg-1)', border: '1px solid var(--line)', borderRadius: 6, marginBottom: 12 }}>
        <Ic name="search" size={13} style={{ color: 'var(--text-3)' }} />
        <input
          value={search}
          onChange={e => setSearch(e.target.value)}
          placeholder="Search scope…"
          style={{ flex: 1, fontSize: 13, background: 'none', color: 'var(--text)' }}
        />
      </div>

      {/* Content */}
      {isLoading ? (
        <div style={{ display: 'flex', justifyContent: 'center', padding: 48 }}><Spinner /></div>
      ) : filtered.length === 0 ? (
        <EmptyState icon="target" title="No scope items" body="Add hosts, IPs, CIDRs, URLs, or wildcards to define the engagement scope." action={
          <Button variant="primary" icon={<Ic name="plus" size={14} />} onClick={() => setAddOpen(true)}>Add first target</Button>
        } />
      ) : view === 'table' ? (
        <Card padding={0}>
          {/* Table header */}
          <div style={{ display: 'grid', gridTemplateColumns: '90px 1fr 80px 1fr 40px', gap: 12, padding: '8px 16px', borderBottom: '1px solid var(--line)', fontSize: 11, color: 'var(--text-3)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
            <span>Type</span><span>Value</span><span>Added</span><span>Notes</span><span />
          </div>
          {filtered.map(item => (
            <ScopeRow key={item.id} item={item} onDelete={() => remove.mutate(item.id)} />
          ))}
        </Card>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 12 }}>
          {filtered.map(item => (
            <ScopeCard key={item.id} item={item} onDelete={() => remove.mutate(item.id)} />
          ))}
        </div>
      )}

      <AddScopeModal open={addOpen} onClose={() => setAddOpen(false)} engagementId={engagement.id} />
    </div>
  )
}

function ScopeRow({ item, onDelete }: { item: ScopeItem; onDelete: () => void }) {
  return (
    <div style={{
      display: 'grid', gridTemplateColumns: '90px 1fr 80px 1fr 40px',
      gap: 12, alignItems: 'center', padding: '10px 16px',
      borderBottom: '1px solid var(--line)',
    }} className="hover-row">
      <Tag tone="neutral">{item.type}</Tag>
      <div style={{ fontFamily: 'var(--mono)', fontSize: 13, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
        {item.value}
      </div>
      <div style={{ fontSize: 11.5, color: 'var(--text-3)' }}>
        {new Date(item.created_at).toLocaleDateString()}
      </div>
      <div style={{ fontSize: 12, color: 'var(--text-3)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
        {item.notes || '—'}
      </div>
      <IconButton icon={<Ic name="trash" size={13} />} onClick={onDelete} style={{ color: 'var(--crit)' }} />
    </div>
  )
}

function ScopeCard({ item, onDelete }: { item: ScopeItem; onDelete: () => void }) {
  const color = typeColors[item.type] || 'var(--text-3)'
  return (
    <Card padding={14} hover>
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 8 }}>
        <span style={{
          padding: '2px 8px', borderRadius: 4, fontSize: 11, fontFamily: 'var(--mono)',
          background: `${color}18`, color, border: `1px solid ${color}44`,
        }}>{item.type}</span>
        <IconButton icon={<Ic name="trash" size={12} />} onClick={onDelete} style={{ color: 'var(--text-4)' }} size={22} />
      </div>
      <div style={{ fontFamily: 'var(--mono)', fontSize: 13.5, fontWeight: 500, marginBottom: 6, overflow: 'hidden', textOverflow: 'ellipsis' }}>
        {item.value}
      </div>
      {item.notes && <div style={{ fontSize: 12, color: 'var(--text-3)' }}>{item.notes}</div>}
      <div style={{ fontSize: 11, color: 'var(--text-4)', marginTop: 8, fontFamily: 'var(--mono)' }}>
        Added {new Date(item.created_at).toLocaleDateString()}
      </div>
    </Card>
  )
}

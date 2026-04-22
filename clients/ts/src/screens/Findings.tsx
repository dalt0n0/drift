import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Ic } from '../components/Icon'
import { Avatar, Button, Card, EmptyState, FieldRow, IconButton, Input, Modal, Select, SevPill, Spinner, StatusPill, Tag, Textarea } from '../components/primitives'
import { getFindings, createFinding, updateFinding, deleteFinding, acceptFinding, rejectFinding } from '../api'
import type { Engagement, Finding, FindingSeverity, FindingStatus } from '../types'

interface Props { engagement: Engagement | null }

const SEVERITIES: FindingSeverity[] = ['critical', 'high', 'medium', 'low', 'info']
const STATUSES: FindingStatus[] = ['open', 'triaged', 'accepted-risk', 'resolved', 'false-positive']

function SuggestedBanner({ findings, engagementId }: { findings: Finding[]; engagementId: string }) {
  const qc = useQueryClient()

  const accept = useMutation({
    mutationFn: (id: string) => acceptFinding(id, engagementId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['findings', engagementId] }),
  })
  const reject = useMutation({
    mutationFn: (id: string) => rejectFinding(id, engagementId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['findings', engagementId] }),
  })

  if (findings.length === 0) return null

  return (
    <div style={{
      margin: '12px 14px 0',
      borderRadius: 8,
      border: '1px solid rgba(255,197,61,0.35)',
      background: 'rgba(255,197,61,0.07)',
      overflow: 'hidden',
    }}>
      <div style={{
        padding: '10px 14px',
        borderBottom: '1px solid rgba(255,197,61,0.2)',
        display: 'flex', alignItems: 'center', gap: 8,
      }}>
        <Ic name="zap" size={14} style={{ color: '#ffc53d' }} />
        <span style={{ fontSize: 13, fontWeight: 600, color: '#ffc53d' }}>
          {findings.length} suggested finding{findings.length !== 1 ? 's' : ''} from automated scans — review required
        </span>
      </div>
      {findings.map(f => (
        <div key={f.id} style={{
          display: 'flex', alignItems: 'center', gap: 10,
          padding: '9px 14px',
          borderBottom: '1px solid rgba(255,197,61,0.12)',
        }}>
          <SevPill sev={f.severity} compact />
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: 13, fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{f.title}</div>
            {f.target && <div style={{ fontSize: 11, color: 'var(--text-3)', fontFamily: 'var(--mono)', marginTop: 2 }}>{f.target}</div>}
          </div>
          <div style={{ display: 'flex', gap: 6, flexShrink: 0 }}>
            <Button
              variant="secondary" size="sm"
              onClick={() => accept.mutate(f.id)}
              disabled={accept.isPending || reject.isPending}
            >Accept</Button>
            <Button
              variant="danger" size="sm"
              onClick={() => reject.mutate(f.id)}
              disabled={accept.isPending || reject.isPending}
            >Reject</Button>
          </div>
        </div>
      ))}
    </div>
  )
}

function FindingDetail({ finding, engagementId, onClose }: { finding: Finding; engagementId: string; onClose: () => void }) {
  const [tab, setTab] = useState<'overview' | 'remediation' | 'edit'>('overview')
  const qc = useQueryClient()

  const statusUpdate = useMutation({
    mutationFn: (status: FindingStatus) => updateFinding(engagementId, finding.id, { status }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['findings', engagementId] }),
  })

  const tabs = ['overview', 'remediation', 'edit'] as const

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', minWidth: 0 }}>
      {/* Detail header */}
      <div style={{ padding: '14px 18px', borderBottom: '1px solid var(--line)', display: 'flex', alignItems: 'flex-start', gap: 12 }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
            <SevPill sev={finding.severity} />
            <StatusPill status={finding.status} />
            {finding.cvss_score && (
              <span style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--text-3)', padding: '2px 6px', background: 'var(--bg-3)', borderRadius: 4 }}>
                CVSS {finding.cvss_score.toFixed(1)}
              </span>
            )}
          </div>
          <div style={{ fontSize: 16, fontWeight: 600, lineHeight: 1.3 }}>{finding.title}</div>
          <div style={{ fontSize: 12, color: 'var(--text-3)', marginTop: 6, display: 'flex', gap: 12 }}>
            {finding.target && <span style={{ fontFamily: 'var(--mono)' }}>{finding.target}</span>}
            {finding.category && <span>{finding.category}</span>}
            {finding.cwe && <span style={{ fontFamily: 'var(--mono)' }}>{finding.cwe}</span>}
          </div>
        </div>
        <IconButton icon={<Ic name="close" size={14} />} onClick={onClose} />
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', gap: 2, padding: '8px 18px 0', borderBottom: '1px solid var(--line)' }}>
        {tabs.map(t => (
          <button key={t} onClick={() => setTab(t)} style={{
            padding: '6px 12px', fontSize: 12.5,
            color: tab === t ? 'var(--text)' : 'var(--text-3)',
            borderBottom: tab === t ? '2px solid var(--accent)' : '2px solid transparent',
            marginBottom: -1, textTransform: 'capitalize',
          }}>{t}</button>
        ))}
      </div>

      <div style={{ flex: 1, overflow: 'auto', padding: '16px 18px' }}>
        {tab === 'overview' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            {finding.description && (
              <div>
                <div style={{ fontSize: 12, color: 'var(--text-3)', marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.06em' }}>Summary</div>
                <div style={{ fontSize: 13, color: 'var(--text-2)', lineHeight: 1.6 }}>{finding.description}</div>
              </div>
            )}

            {finding.tags && finding.tags.length > 0 && (
              <div>
                <div style={{ fontSize: 12, color: 'var(--text-3)', marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.06em' }}>Tags</div>
                <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                  {finding.tags.map(t => <Tag key={t}>{t}</Tag>)}
                </div>
              </div>
            )}

            {finding.cve_ids && finding.cve_ids.length > 0 && (
              <div>
                <div style={{ fontSize: 12, color: 'var(--text-3)', marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.06em' }}>CVEs</div>
                <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                  {finding.cve_ids.map(c => <Tag key={c} tone="warn">{c}</Tag>)}
                </div>
              </div>
            )}

            {/* Quick status change */}
            <div>
              <div style={{ fontSize: 12, color: 'var(--text-3)', marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.06em' }}>Update status</div>
              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                {STATUSES.map(s => (
                  <button key={s} onClick={() => statusUpdate.mutate(s)} style={{
                    padding: '4px 10px', borderRadius: 6, fontSize: 12,
                    background: finding.status === s ? 'var(--accent-bg)' : 'var(--bg-3)',
                    color: finding.status === s ? 'var(--accent)' : 'var(--text-2)',
                    border: `1px solid ${finding.status === s ? 'var(--accent-line)' : 'var(--line)'}`,
                    cursor: 'pointer',
                  }}>{s}</button>
                ))}
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
              <div style={{ padding: 12, background: 'var(--bg-2)', borderRadius: 6 }}>
                <div style={{ fontSize: 11, color: 'var(--text-3)', marginBottom: 4 }}>Reporter</div>
                <div style={{ fontSize: 12.5, display: 'flex', alignItems: 'center', gap: 6 }}>
                  {finding.reporter_id ? <><Avatar id={finding.reporter_id} size={18} /> {finding.reporter_id}</> : '—'}
                </div>
              </div>
              <div style={{ padding: 12, background: 'var(--bg-2)', borderRadius: 6 }}>
                <div style={{ fontSize: 11, color: 'var(--text-3)', marginBottom: 4 }}>Assignee</div>
                <div style={{ fontSize: 12.5, display: 'flex', alignItems: 'center', gap: 6 }}>
                  {finding.assignee_id ? <><Avatar id={finding.assignee_id} size={18} /> {finding.assignee_id}</> : 'Unassigned'}
                </div>
              </div>
              <div style={{ padding: 12, background: 'var(--bg-2)', borderRadius: 6 }}>
                <div style={{ fontSize: 11, color: 'var(--text-3)', marginBottom: 4 }}>Created</div>
                <div style={{ fontSize: 12.5, fontFamily: 'var(--mono)' }}>{new Date(finding.created_at).toLocaleString()}</div>
              </div>
              <div style={{ padding: 12, background: 'var(--bg-2)', borderRadius: 6 }}>
                <div style={{ fontSize: 11, color: 'var(--text-3)', marginBottom: 4 }}>Updated</div>
                <div style={{ fontSize: 12.5, fontFamily: 'var(--mono)' }}>{new Date(finding.updated_at).toLocaleString()}</div>
              </div>
            </div>
          </div>
        )}

        {tab === 'remediation' && (
          <div>
            {finding.remediation ? (
              <div style={{ fontSize: 13, color: 'var(--text-2)', lineHeight: 1.7 }}>{finding.remediation}</div>
            ) : (
              <EmptyState icon="shield" title="No remediation guidance" body="Edit this finding to add remediation steps." />
            )}
          </div>
        )}

        {tab === 'edit' && (
          <EditFindingForm finding={finding} engagementId={engagementId} />
        )}
      </div>
    </div>
  )
}

function EditFindingForm({ finding, engagementId }: { finding: Finding; engagementId: string }) {
  const qc = useQueryClient()
  const [title, setTitle] = useState(finding.title)
  const [description, setDescription] = useState(finding.description || '')
  const [severity, setSeverity] = useState<FindingSeverity>(finding.severity)
  const [status, setStatus] = useState<FindingStatus>(finding.status)
  const [target, setTarget] = useState(finding.target || '')
  const [category, setCategory] = useState(finding.category || '')
  const [cwe, setCwe] = useState(finding.cwe || '')
  const [remediation, setRemediation] = useState(finding.remediation || '')
  const [saved, setSaved] = useState(false)

  const update = useMutation({
    mutationFn: () => updateFinding(engagementId, finding.id, { title, description, severity, status, target, category, cwe, remediation }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['findings', engagementId] }); setSaved(true); setTimeout(() => setSaved(false), 2000) },
  })

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      <FieldRow label="Title"><Input value={title} onChange={setTitle} /></FieldRow>
      <FieldRow label="Description"><Textarea value={description} onChange={setDescription} rows={4} /></FieldRow>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        <FieldRow label="Severity">
          <Select value={severity} onChange={v => setSeverity(v as FindingSeverity)}>
            {SEVERITIES.map(s => <option key={s} value={s}>{s}</option>)}
          </Select>
        </FieldRow>
        <FieldRow label="Status">
          <Select value={status} onChange={v => setStatus(v as FindingStatus)}>
            {STATUSES.map(s => <option key={s} value={s}>{s}</option>)}
          </Select>
        </FieldRow>
        <FieldRow label="Target"><Input value={target} onChange={setTarget} placeholder="api.example.com" /></FieldRow>
        <FieldRow label="Category"><Input value={category} onChange={setCategory} placeholder="Injection" /></FieldRow>
        <FieldRow label="CWE"><Input value={cwe} onChange={setCwe} placeholder="CWE-89" /></FieldRow>
      </div>
      <FieldRow label="Remediation"><Textarea value={remediation} onChange={setRemediation} rows={4} /></FieldRow>
      <Button variant="primary" onClick={() => update.mutate()} disabled={update.isPending}>
        {saved ? '✓ Saved' : update.isPending ? 'Saving…' : 'Save changes'}
      </Button>
    </div>
  )
}

function NewFindingModal({ open, onClose, engagementId }: { open: boolean; onClose: () => void; engagementId: string }) {
  const qc = useQueryClient()
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [severity, setSeverity] = useState<FindingSeverity>('medium')
  const [target, setTarget] = useState('')
  const [category, setCategory] = useState('')

  const create = useMutation({
    mutationFn: () => createFinding(engagementId, { title, description, severity, status: 'open', target, category }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['findings', engagementId] }); onClose() },
  })

  return (
    <Modal open={open} onClose={onClose} title="New finding" width={520}>
      <div style={{ padding: 20, display: 'flex', flexDirection: 'column', gap: 14 }}>
        <FieldRow label="Title *"><Input value={title} onChange={setTitle} placeholder="SQL Injection in /api/orders" /></FieldRow>
        <FieldRow label="Description"><Textarea value={description} onChange={setDescription} placeholder="Describe the finding…" rows={3} /></FieldRow>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
          <FieldRow label="Severity">
            <Select value={severity} onChange={v => setSeverity(v as FindingSeverity)}>
              {SEVERITIES.map(s => <option key={s} value={s}>{s}</option>)}
            </Select>
          </FieldRow>
          <FieldRow label="Target"><Input value={target} onChange={setTarget} placeholder="api.example.com" /></FieldRow>
          <FieldRow label="Category"><Input value={category} onChange={setCategory} placeholder="Injection" /></FieldRow>
        </div>
        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', paddingTop: 4 }}>
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button variant="primary" onClick={() => create.mutate()} disabled={!title || create.isPending}>
            {create.isPending ? 'Creating…' : 'Create finding'}
          </Button>
        </div>
      </div>
    </Modal>
  )
}

export default function Findings({ engagement }: Props) {
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [filter, setFilter] = useState<string>('all')
  const [search, setSearch] = useState('')
  const [newOpen, setNewOpen] = useState(false)

  const { data: findings = [], isLoading } = useQuery({
    queryKey: ['findings', engagement?.id],
    queryFn: () => getFindings(engagement!.id),
    enabled: !!engagement?.id,
  })

  if (!engagement) return <EmptyState icon="bug" title="No engagement selected" />

  const suggested = findings.filter(f => f.status === 'suggested')
  const nonSuggested = findings.filter(f => f.status !== 'suggested')

  const filtered = nonSuggested.filter(f => {
    if (filter === 'open') return f.status === 'open' || f.status === 'triaged'
    if (filter === 'critical') return f.severity === 'critical' || f.severity === 'high'
    if (filter === 'resolved') return f.status === 'resolved'
    return true
  }).filter(f => !search || f.title.toLowerCase().includes(search.toLowerCase()) || f.target?.includes(search))

  const selected = findings.find(f => f.id === selectedId) || null

  const filterTabs = [
    { id: 'all', label: 'All', count: nonSuggested.length },
    { id: 'open', label: 'Open', count: nonSuggested.filter(f => f.status === 'open' || f.status === 'triaged').length },
    { id: 'critical', label: 'Critical/High', count: nonSuggested.filter(f => f.severity === 'critical' || f.severity === 'high').length },
    { id: 'resolved', label: 'Resolved', count: nonSuggested.filter(f => f.status === 'resolved').length },
  ]

  return (
    <div style={{ display: 'flex', height: 'calc(100vh - 46px)' }}>
      {/* Left: list */}
      <div style={{
        width: 440, flexShrink: 0,
        borderRight: '1px solid var(--line)',
        display: 'flex', flexDirection: 'column',
        background: 'var(--bg-1)',
      }}>
        {/* Header */}
        <div style={{ padding: '12px 14px 10px', borderBottom: '1px solid var(--line)' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
            <div style={{ fontSize: 14, fontWeight: 600 }}>Findings</div>
            <Button variant="primary" size="sm" icon={<Ic name="plus" size={13} />} onClick={() => setNewOpen(true)}>New</Button>
          </div>
          {/* Search */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '5px 10px', height: 30, background: 'var(--bg-2)', border: '1px solid var(--line)', borderRadius: 6, color: 'var(--text-3)', fontSize: 12 }}>
            <Ic name="search" size={13} />
            <input
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder="Search findings…"
              style={{ flex: 1, background: 'none', fontSize: 12.5, color: 'var(--text)' }}
            />
          </div>
          {/* Filters */}
          <div style={{ display: 'flex', gap: 2, marginTop: 8, borderBottom: '1px solid var(--line)', paddingBottom: 0, marginBottom: -10 }}>
            {filterTabs.map(t => (
              <button key={t.id} onClick={() => setFilter(t.id)} style={{
                padding: '5px 8px', fontSize: 11.5,
                color: filter === t.id ? 'var(--text)' : 'var(--text-3)',
                borderBottom: filter === t.id ? '2px solid var(--accent)' : '2px solid transparent',
                marginBottom: -1,
              }}>
                {t.label}
                <span style={{ marginLeft: 5, color: 'var(--text-4)', fontFamily: 'var(--mono)', fontSize: 11 }}>{t.count}</span>
              </button>
            ))}
          </div>
        </div>

        {/* Suggested findings banner */}
        <SuggestedBanner findings={suggested} engagementId={engagement.id} />

        {/* List */}
        <div style={{ flex: 1, overflow: 'auto' }}>
          {isLoading ? (
            <div style={{ display: 'flex', justifyContent: 'center', padding: 32 }}><Spinner /></div>
          ) : filtered.length === 0 ? (
            <EmptyState icon="bug" title="No findings" body={search ? 'Try a different search.' : 'Add a finding to get started.'} />
          ) : (
            filtered.map(f => (
              <div
                key={f.id}
                onClick={() => setSelectedId(f.id)}
                className="hover-row"
                style={{
                  padding: '10px 14px',
                  borderBottom: '1px solid var(--line)',
                  cursor: 'pointer',
                  background: selectedId === f.id ? 'var(--bg-2)' : 'transparent',
                  borderLeft: selectedId === f.id ? '2px solid var(--accent)' : '2px solid transparent',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 5 }}>
                  <SevPill sev={f.severity} compact />
                  <StatusPill status={f.status} />
                  <div style={{ flex: 1 }} />
                  {f.cvss_score && (
                    <span style={{ fontSize: 10.5, fontFamily: 'var(--mono)', color: 'var(--text-4)' }}>
                      {f.cvss_score.toFixed(1)}
                    </span>
                  )}
                </div>
                <div style={{ fontSize: 13, fontWeight: 500, lineHeight: 1.35, marginBottom: 4 }}>{f.title}</div>
                <div style={{ fontSize: 11, color: 'var(--text-3)', display: 'flex', gap: 8 }}>
                  {f.target && <span style={{ fontFamily: 'var(--mono)' }}>{f.target}</span>}
                  {f.category && <span>{f.category}</span>}
                  <span style={{ marginLeft: 'auto' }}>{new Date(f.updated_at).toLocaleDateString()}</span>
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Right: detail */}
      <div style={{ flex: 1, minWidth: 0, overflow: 'auto', background: 'var(--bg)' }}>
        {selected ? (
          <FindingDetail finding={selected} engagementId={engagement.id} onClose={() => setSelectedId(null)} />
        ) : (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%' }}>
            <EmptyState icon="bug" title="Select a finding" body="Choose a finding from the list to view details." />
          </div>
        )}
      </div>

      <NewFindingModal open={newOpen} onClose={() => setNewOpen(false)} engagementId={engagement.id} />
    </div>
  )
}

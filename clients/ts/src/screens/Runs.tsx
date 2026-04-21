import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Ic } from '../components/Icon'
import { Button, Card, EmptyState, FieldRow, Input, Modal, Select, Spinner, Tag } from '../components/primitives'
import { getRuns, createRun } from '../api'
import type { Engagement, EngagementRun } from '../types'

interface Props { engagement: Engagement | null }

const PLUGINS = [
  { id: 'subfinder', label: 'Subfinder — subdomain enum', category: 'recon' },
  { id: 'httpx_probe', label: 'httpx — HTTP probing', category: 'recon' },
  { id: 'nmap_scan', label: 'Nmap — port scan', category: 'active' },
  { id: 'nuclei_scan', label: 'Nuclei — vuln templates', category: 'active' },
  { id: 'nikto_scan', label: 'Nikto — web scanner', category: 'web' },
  { id: 'gobuster_dir', label: 'Gobuster — dir brute-force', category: 'web' },
  { id: 'ffuf_fuzz', label: 'ffuf — web fuzzer', category: 'web' },
  { id: 'sslyze', label: 'SSLyze — TLS analysis', category: 'crypto' },
  { id: 'enum4linux_ng', label: 'enum4linux-ng — SMB enum', category: 'network' },
]

const statusColors: Record<string, string> = {
  pending: '#7a828f', running: '#ffaa00', completed: '#34d399', failed: '#ff4a5e', error: '#ff4a5e',
}

function LaunchModal({ open, onClose, engagementId }: { open: boolean; onClose: () => void; engagementId: string }) {
  const qc = useQueryClient()
  const [plugin, setPlugin] = useState(PLUGINS[0].id)
  const [target, setTarget] = useState('')
  const [extraFlags, setExtraFlags] = useState('')

  const run = useMutation({
    mutationFn: () => createRun(engagementId, plugin, { target, flags: extraFlags }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['runs', engagementId] }); onClose() },
  })

  return (
    <Modal open={open} onClose={onClose} title="Launch scan" width={500}>
      <div style={{ padding: 20, display: 'flex', flexDirection: 'column', gap: 14 }}>
        <FieldRow label="Plugin">
          <Select value={plugin} onChange={setPlugin}>
            {PLUGINS.map(p => <option key={p.id} value={p.id}>{p.label}</option>)}
          </Select>
        </FieldRow>
        <FieldRow label="Target *">
          <Input value={target} onChange={setTarget} placeholder="api.example.com or https://example.com" />
        </FieldRow>
        <FieldRow label="Extra flags">
          <Input value={extraFlags} onChange={setExtraFlags} placeholder="-Tuning 1 2 3" />
        </FieldRow>
        <div style={{ padding: '10px 12px', background: 'var(--bg-2)', borderRadius: 6, fontSize: 12, color: 'var(--text-3)' }}>
          All runs are scope-validated before execution. Out-of-scope targets will be rejected.
        </div>
        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button variant="primary" icon={<Ic name="play" size={13} />} onClick={() => run.mutate()} disabled={!target || run.isPending}>
            {run.isPending ? 'Launching…' : 'Launch'}
          </Button>
        </div>
      </div>
    </Modal>
  )
}

function RunDetail({ run }: { run: EngagementRun }) {
  const [tab, setTab] = useState<'stdout' | 'stderr'>('stdout')
  const statusColor = statusColors[run.status] || 'var(--text-3)'

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div style={{ padding: '14px 18px', borderBottom: '1px solid var(--line)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
          <span style={{ width: 8, height: 8, borderRadius: 999, background: statusColor, boxShadow: run.status === 'running' ? `0 0 0 3px ${statusColor}33` : 'none' }} />
          <span style={{ fontSize: 12, color: statusColor, fontFamily: 'var(--mono)', textTransform: 'uppercase' }}>{run.status}</span>
          <span style={{ fontSize: 12, color: 'var(--text-3)', fontFamily: 'var(--mono)' }}>·</span>
          <span style={{ fontSize: 12, fontFamily: 'var(--mono)', color: 'var(--text-2)' }}>{run.plugin}</span>
        </div>
        <div style={{ fontSize: 13, color: 'var(--text-3)' }}>
          {run.params && typeof run.params === 'object' && (run.params as Record<string, string>).target && (
            <span style={{ fontFamily: 'var(--mono)' }}>{(run.params as Record<string, string>).target}</span>
          )}
        </div>
        <div style={{ display: 'flex', gap: 16, marginTop: 8, fontSize: 11.5, color: 'var(--text-3)' }}>
          {run.started_at && <span>Started: {new Date(run.started_at).toLocaleString()}</span>}
          {run.finished_at && <span>Finished: {new Date(run.finished_at).toLocaleString()}</span>}
        </div>
      </div>
      <div style={{ display: 'flex', gap: 2, padding: '6px 18px 0', borderBottom: '1px solid var(--line)' }}>
        {(['stdout', 'stderr'] as const).map(t => (
          <button key={t} onClick={() => setTab(t)} style={{
            padding: '5px 10px', fontSize: 12,
            color: tab === t ? 'var(--text)' : 'var(--text-3)',
            borderBottom: tab === t ? '2px solid var(--accent)' : '2px solid transparent',
            marginBottom: -1, fontFamily: 'var(--mono)',
          }}>{t}</button>
        ))}
      </div>
      <div style={{ flex: 1, overflow: 'auto', padding: '14px 18px', background: 'var(--bg-2)' }}>
        <pre style={{ fontFamily: 'var(--mono)', fontSize: 12, color: 'var(--text-2)', whiteSpace: 'pre-wrap', lineHeight: 1.6 }}>
          {tab === 'stdout' ? (run.stdout || '(no output)') : (run.stderr || '(no stderr)')}
        </pre>
      </div>
    </div>
  )
}

export default function Runs({ engagement }: Props) {
  const [launchOpen, setLaunchOpen] = useState(false)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [statusFilter, setStatusFilter] = useState('all')

  const { data: runs = [], isLoading } = useQuery({
    queryKey: ['runs', engagement?.id],
    queryFn: () => getRuns(engagement!.id),
    enabled: !!engagement?.id,
    refetchInterval: 5000,
  })

  if (!engagement) return <EmptyState icon="terminal" title="No engagement selected" />

  const filtered = runs.filter(r => statusFilter === 'all' || r.status === statusFilter)
  const selected = runs.find(r => r.id === selectedId) || null

  return (
    <div style={{ display: 'flex', height: 'calc(100vh - 46px)' }}>
      {/* List */}
      <div style={{ width: 380, flexShrink: 0, borderRight: '1px solid var(--line)', display: 'flex', flexDirection: 'column', background: 'var(--bg-1)' }}>
        <div style={{ padding: '12px 14px', borderBottom: '1px solid var(--line)' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
            <div style={{ fontSize: 14, fontWeight: 600 }}>Scan runs</div>
            <Button variant="primary" size="sm" icon={<Ic name="play" size={13} />} onClick={() => setLaunchOpen(true)}>Launch</Button>
          </div>
          <div style={{ display: 'flex', gap: 2 }}>
            {['all', 'running', 'completed', 'failed'].map(s => (
              <button key={s} onClick={() => setStatusFilter(s)} style={{
                padding: '3px 8px', fontSize: 11, borderRadius: 4, textTransform: 'capitalize',
                background: statusFilter === s ? 'var(--bg-3)' : 'transparent',
                color: statusFilter === s ? 'var(--text)' : 'var(--text-3)',
              }}>{s}</button>
            ))}
          </div>
        </div>
        <div style={{ flex: 1, overflow: 'auto' }}>
          {isLoading ? (
            <div style={{ display: 'flex', justifyContent: 'center', padding: 32 }}><Spinner /></div>
          ) : filtered.length === 0 ? (
            <EmptyState icon="terminal" title="No runs" body="Launch a scan to start collecting data." />
          ) : filtered.map(r => (
            <div key={r.id} onClick={() => setSelectedId(r.id)} className="hover-row" style={{
              padding: '10px 14px', borderBottom: '1px solid var(--line)', cursor: 'pointer',
              background: selectedId === r.id ? 'var(--bg-2)' : 'transparent',
              borderLeft: selectedId === r.id ? '2px solid var(--accent)' : '2px solid transparent',
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                <span style={{ width: 7, height: 7, borderRadius: 999, background: statusColors[r.status] || 'var(--text-3)', flexShrink: 0 }} />
                <span style={{ fontFamily: 'var(--mono)', fontSize: 12.5, fontWeight: 500 }}>{r.plugin}</span>
                <span style={{ fontSize: 11, color: 'var(--text-4)', marginLeft: 'auto', fontFamily: 'var(--mono)', textTransform: 'uppercase' }}>{r.status}</span>
              </div>
              <div style={{ fontSize: 12, color: 'var(--text-3)', fontFamily: 'var(--mono)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {(r.params as Record<string, string>)?.target || '—'}
              </div>
              <div style={{ fontSize: 11, color: 'var(--text-4)', marginTop: 4 }}>
                {new Date(r.created_at).toLocaleString()}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Detail */}
      <div style={{ flex: 1, minWidth: 0, background: 'var(--bg)' }}>
        {selected ? (
          <RunDetail run={selected} />
        ) : (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%' }}>
            <EmptyState icon="terminal" title="Select a run" body="Click a run to view its output." action={
              <Button variant="secondary" icon={<Ic name="play" size={13} />} onClick={() => setLaunchOpen(true)}>Launch new scan</Button>
            } />
          </div>
        )}
      </div>

      <LaunchModal open={launchOpen} onClose={() => setLaunchOpen(false)} engagementId={engagement.id} />
    </div>
  )
}

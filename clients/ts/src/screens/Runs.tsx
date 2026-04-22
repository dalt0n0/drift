import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Ic } from '../components/Icon'
import { Button, Card, EmptyState, FieldRow, Input, Modal, Select, Spinner, Tag } from '../components/primitives'
import { getRuns, createRun, confirmAuthorization } from '../api'
import type { Engagement, EngagementRun } from '../types'

interface Props { engagement: Engagement | null }

const PLUGINS = [
  { id: 'subfinder', label: 'Subfinder — subdomain enum', category: 'recon' },
  { id: 'httpx', label: 'httpx — HTTP probing', category: 'recon' },
  { id: 'nmap', label: 'Nmap — port scan', category: 'active' },
  { id: 'nuclei', label: 'Nuclei — vuln templates', category: 'active' },
  { id: 'nikto', label: 'Nikto — web scanner', category: 'web' },
  { id: 'gobuster', label: 'Gobuster — dir brute-force', category: 'web' },
  { id: 'ffuf', label: 'ffuf — web fuzzer', category: 'web' },
  { id: 'sslyze', label: 'SSLyze — TLS analysis', category: 'crypto' },
  { id: 'enum4linux_ng', label: 'enum4linux-ng — SMB enum', category: 'network' },
]

const statusColors: Record<string, string> = {
  pending: '#7a828f', running: '#ffaa00', completed: '#34d399',
  failed: '#ff4a5e', error: '#ff4a5e', cancelled: '#7a828f',
}

function LaunchModal({
  open, onClose, engagement,
}: {
  open: boolean
  onClose: () => void
  engagement: Engagement
}) {
  const qc = useQueryClient()
  const [plugin, setPlugin] = useState(PLUGINS[0].id)
  const [target, setTarget] = useState('')
  const [extraFlags, setExtraFlags] = useState('')
  const [runError, setRunError] = useState('')

  const run = useMutation({
    mutationFn: () => createRun(engagement.id, plugin, { target, flags: extraFlags }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['runs', engagement.id] })
      setRunError('')
      onClose()
    },
    onError: (err: unknown) => {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setRunError(typeof detail === 'string' ? detail : 'Failed to launch scan.')
    },
  })

  const isAuthError = runError.toLowerCase().includes('authorization')

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

        {runError && (
          <div style={{
            padding: '10px 12px', borderRadius: 6,
            background: 'rgba(255,74,94,0.10)', border: '1px solid rgba(255,74,94,0.25)',
            color: 'var(--crit)', fontSize: 12.5,
            display: 'flex', flexDirection: 'column', gap: 6,
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <Ic name="alertTriangle" size={13} />
              {runError}
            </div>
            {isAuthError && (
              <div style={{ fontSize: 12, color: 'var(--text-2)', paddingLeft: 21 }}>
                This engagement needs authorization confirmed before running intrusive plugins.
                Close this dialog and click <strong>Authorize</strong> in the runs header.
              </div>
            )}
          </div>
        )}

        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button
            variant="primary"
            icon={<Ic name="play" size={13} />}
            onClick={() => run.mutate()}
            disabled={!target || run.isPending}
          >
            {run.isPending ? 'Launching…' : 'Launch'}
          </Button>
        </div>
      </div>
    </Modal>
  )
}

function RunDetail({ run }: { run: EngagementRun }) {
  const statusColor = statusColors[run.status] || 'var(--text-3)'
  const plugins = run.pipeline_config?.plugins ?? []
  const params = run.pipeline_config?.params ?? {}
  const completed = run.checkpoint?.completed_plugins ?? []

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div style={{ padding: '14px 18px', borderBottom: '1px solid var(--line)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
          <span style={{
            width: 8, height: 8, borderRadius: 999, background: statusColor,
            boxShadow: run.status === 'running' ? `0 0 0 3px ${statusColor}33` : 'none',
          }} />
          <span style={{ fontSize: 12, color: statusColor, fontFamily: 'var(--mono)', textTransform: 'uppercase' }}>
            {run.status}
          </span>
          {plugins[0] && (
            <>
              <span style={{ fontSize: 12, color: 'var(--text-3)', fontFamily: 'var(--mono)' }}>·</span>
              <span style={{ fontSize: 12, fontFamily: 'var(--mono)', color: 'var(--text-2)' }}>
                {plugins.join(', ')}
              </span>
            </>
          )}
        </div>
        {(params as Record<string, string>).target && (
          <div style={{ fontSize: 13, color: 'var(--text-3)' }}>
            <span style={{ fontFamily: 'var(--mono)' }}>{(params as Record<string, string>).target}</span>
          </div>
        )}
        <div style={{ display: 'flex', gap: 16, marginTop: 8, fontSize: 11.5, color: 'var(--text-3)' }}>
          {run.started_at && <span>Started: {new Date(run.started_at).toLocaleString()}</span>}
          {run.completed_at && <span>Finished: {new Date(run.completed_at).toLocaleString()}</span>}
        </div>
      </div>

      <div style={{ flex: 1, overflow: 'auto', padding: '14px 18px' }}>
        {run.error_message && (
          <div style={{
            marginBottom: 12, padding: '10px 12px', borderRadius: 6,
            background: 'rgba(255,74,94,0.10)', border: '1px solid rgba(255,74,94,0.25)',
            color: 'var(--crit)', fontSize: 12.5,
          }}>
            <Ic name="alertTriangle" size={13} style={{ marginRight: 8 }} />
            {run.error_message}
          </div>
        )}

        <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-2)', marginBottom: 8 }}>Pipeline</div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          {plugins.map(p => (
            <div key={p} style={{
              display: 'flex', alignItems: 'center', gap: 8,
              padding: '6px 10px', borderRadius: 6,
              background: 'var(--bg-2)',
            }}>
              <span style={{
                width: 7, height: 7, borderRadius: 999, flexShrink: 0,
                background: completed.includes(p)
                  ? 'var(--ok)'
                  : run.checkpoint?.current_plugin === p
                    ? '#ffaa00'
                    : 'var(--text-4)',
              }} />
              <span style={{ fontFamily: 'var(--mono)', fontSize: 12 }}>{p}</span>
              <span style={{ fontSize: 11, color: 'var(--text-4)', marginLeft: 'auto' }}>
                {completed.includes(p) ? 'done' : run.checkpoint?.current_plugin === p ? 'running' : 'queued'}
              </span>
            </div>
          ))}
          {plugins.length === 0 && (
            <div style={{ color: 'var(--text-4)', fontSize: 12 }}>No pipeline configured.</div>
          )}
        </div>
      </div>
    </div>
  )
}

export default function Runs({ engagement }: Props) {
  const qc = useQueryClient()
  const [launchOpen, setLaunchOpen] = useState(false)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [statusFilter, setStatusFilter] = useState('all')

  const { data: runs = [], isLoading } = useQuery({
    queryKey: ['runs', engagement?.id],
    queryFn: () => getRuns(engagement!.id),
    enabled: !!engagement?.id,
    refetchInterval: 5000,
  })

  const confirmAuth = useMutation({
    mutationFn: () => confirmAuthorization(engagement!.id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['engagements'] })
      qc.invalidateQueries({ queryKey: ['engagement', engagement!.id] })
    },
  })

  if (!engagement) return <EmptyState icon="terminal" title="No engagement selected" />

  const filtered = runs.filter(r => statusFilter === 'all' || r.status === statusFilter)
  const selected = runs.find(r => r.id === selectedId) || null
  const authorized = engagement.authorization_confirmed

  return (
    <div style={{ display: 'flex', height: 'calc(100vh - 46px)' }}>
      {/* List */}
      <div style={{ width: 380, flexShrink: 0, borderRight: '1px solid var(--line)', display: 'flex', flexDirection: 'column', background: 'var(--bg-1)' }}>
        <div style={{ padding: '12px 14px', borderBottom: '1px solid var(--line)' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
            <div style={{ fontSize: 14, fontWeight: 600 }}>Scan runs</div>
            <div style={{ display: 'flex', gap: 6 }}>
              {!authorized && (
                <Button
                  variant="secondary"
                  size="sm"
                  icon={<Ic name="shield" size={13} />}
                  onClick={() => confirmAuth.mutate()}
                  disabled={confirmAuth.isPending}
                  title="Confirm authorization to enable intrusive scans"
                >
                  {confirmAuth.isPending ? 'Authorizing…' : 'Authorize'}
                </Button>
              )}
              {authorized && (
                <div style={{
                  display: 'flex', alignItems: 'center', gap: 4,
                  padding: '3px 8px', borderRadius: 4, fontSize: 11,
                  background: 'rgba(52,211,153,0.12)', color: 'var(--ok)',
                  border: '1px solid rgba(52,211,153,0.25)',
                }}>
                  <Ic name="shield" size={11} /> Authorized
                </div>
              )}
              <Button variant="primary" size="sm" icon={<Ic name="play" size={13} />} onClick={() => setLaunchOpen(true)}>Launch</Button>
            </div>
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
          ) : filtered.map(r => {
            const plugins = r.pipeline_config?.plugins ?? []
            const target = (r.pipeline_config?.params as Record<string, string>)?.target
            return (
              <div key={r.id} onClick={() => setSelectedId(r.id)} className="hover-row" style={{
                padding: '10px 14px', borderBottom: '1px solid var(--line)', cursor: 'pointer',
                background: selectedId === r.id ? 'var(--bg-2)' : 'transparent',
                borderLeft: selectedId === r.id ? '2px solid var(--accent)' : '2px solid transparent',
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                  <span style={{ width: 7, height: 7, borderRadius: 999, background: statusColors[r.status] || 'var(--text-3)', flexShrink: 0 }} />
                  <span style={{ fontFamily: 'var(--mono)', fontSize: 12.5, fontWeight: 500 }}>
                    {plugins[0] ?? '—'}
                  </span>
                  <span style={{ fontSize: 11, color: 'var(--text-4)', marginLeft: 'auto', fontFamily: 'var(--mono)', textTransform: 'uppercase' }}>{r.status}</span>
                </div>
                {target && (
                  <div style={{ fontSize: 12, color: 'var(--text-3)', fontFamily: 'var(--mono)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {target}
                  </div>
                )}
                <div style={{ fontSize: 11, color: 'var(--text-4)', marginTop: 4 }}>
                  {new Date(r.created_at).toLocaleString()}
                </div>
              </div>
            )
          })}
        </div>
      </div>

      {/* Detail */}
      <div style={{ flex: 1, minWidth: 0, background: 'var(--bg)' }}>
        {selected ? (
          <RunDetail run={selected} />
        ) : (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%' }}>
            <EmptyState icon="terminal" title="Select a run" body="Click a run to view its details." action={
              <Button variant="secondary" icon={<Ic name="play" size={13} />} onClick={() => setLaunchOpen(true)}>Launch new scan</Button>
            } />
          </div>
        )}
      </div>

      <LaunchModal open={launchOpen} onClose={() => setLaunchOpen(false)} engagement={engagement} />
    </div>
  )
}

import { useQuery } from '@tanstack/react-query'
import { Ic } from '../components/Icon'
import { Avatar, AvatarStack, Button, Card, KPI, SevPill, SeverityBar, Progress, Sparkline, SectionHeader, StatusPill, EmptyState, Spinner } from '../components/primitives'
import { getEngagements, getFindings, getRuns } from '../api'
import type { Engagement, Finding } from '../types'

interface Props {
  engagement: Engagement | null
  onNav: (id: string) => void
}

const phases = ['Scoping', 'Recon', 'Discovery', 'Exploitation', 'Reporting', 'Review']

function getPhaseProgress(phase: string | undefined) {
  if (!phase) return 0
  const idx = phases.findIndex(p => p.toLowerCase() === phase.toLowerCase())
  return idx < 0 ? 0 : idx / (phases.length - 1)
}

function countSeverities(findings: Finding[]) {
  const out = { critical: 0, high: 0, medium: 0, low: 0, info: 0 }
  for (const f of findings) out[f.severity] = (out[f.severity] || 0) + 1
  return out
}

export default function Dashboard({ engagement, onNav }: Props) {
  const { data: engagements = [] } = useQuery({ queryKey: ['engagements'], queryFn: getEngagements })
  const { data: findings = [], isLoading: findingsLoading } = useQuery({
    queryKey: ['findings', engagement?.id],
    queryFn: () => getFindings(engagement!.id),
    enabled: !!engagement?.id,
  })
  const { data: runs = [] } = useQuery({
    queryKey: ['runs', engagement?.id],
    queryFn: () => getRuns(engagement!.id),
    enabled: !!engagement?.id,
  })

  if (!engagement) return (
    <EmptyState icon="dashboard" title="No engagement selected" body="Create or select an engagement to get started." />
  )

  const counts = countSeverities(findings)
  const total = findings.length
  const open = findings.filter(f => f.status === 'open' || f.status === 'triaged').length
  const resolved = findings.filter(f => f.status === 'resolved').length
  const progress = getPhaseProgress(engagement.engagement_type)
  const sparkData = [2, 4, 3, 6, 5, 8, 7, 10, open]

  const startDate = engagement.start_date ? new Date(engagement.start_date).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) : '—'
  const endDate = engagement.end_date ? new Date(engagement.end_date).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) : '—'

  return (
    <div style={{ padding: '22px 24px', maxWidth: 1400 }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 20, gap: 20 }}>
        <div style={{ flex: 1 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6 }}>
            <div style={{
              width: 8, height: 8, borderRadius: 999, background: 'var(--ok)',
              boxShadow: '0 0 0 3px rgba(52,211,153,0.15)',
            }} />
            <span style={{ fontSize: 11, fontFamily: 'var(--mono)', color: 'var(--text-3)', letterSpacing: '0.04em', textTransform: 'uppercase' }}>
              {engagement.status} · {engagement.engagement_type || 'External'}
            </span>
          </div>
          <div style={{ fontSize: 24, fontWeight: 600, letterSpacing: '-0.025em', marginBottom: 8 }}>
            {engagement.name}
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 16, color: 'var(--text-3)', fontSize: 12.5 }}>
            <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <Ic name="calendar" size={13} /> {startDate} → {endDate}
            </span>
            <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <Ic name="bug" size={13} /> {total} findings
            </span>
            <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <Ic name="terminal" size={13} /> {runs.length} runs
            </span>
          </div>
        </div>
        <div style={{ display: 'flex', gap: 6 }}>
          <Button variant="ghost" icon={<Ic name="download" size={14} />}>Export</Button>
          <Button variant="secondary" icon={<Ic name="play" size={13} />} onClick={() => onNav('runs')}>Run scan</Button>
          <Button variant="primary" icon={<Ic name="plus" size={14} />} onClick={() => onNav('findings')}>New finding</Button>
        </div>
      </div>

      {/* Phase progress */}
      <Card padding={16} style={{ marginBottom: 20 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
          <div style={{ fontSize: 12.5, fontWeight: 500 }}>Engagement progress</div>
          <div style={{ fontSize: 12, color: 'var(--text-3)', fontFamily: 'var(--mono)' }}>
            {engagement.status} · {engagement.engagement_type || 'External Web'}
          </div>
        </div>
        <div style={{ position: 'relative', height: 24 }}>
          <div style={{ position: 'absolute', inset: '10px 0', height: 4, background: 'var(--bg-3)', borderRadius: 999 }} />
          <div style={{ position: 'absolute', left: 0, top: 10, height: 4, width: `${progress * 100}%`, background: 'linear-gradient(90deg, var(--accent) 0%, #ffcc55 100%)', borderRadius: 999 }} />
          {phases.map((p, i, arr) => {
            const pct = i / (arr.length - 1)
            const current = engagement.status === p.toLowerCase() || engagement.engagement_type === p
            return (
              <div key={p} style={{ position: 'absolute', left: `${pct * 100}%`, top: 0, transform: 'translateX(-50%)', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 3 }}>
                <div style={{
                  width: current ? 12 : 8, height: current ? 12 : 8, borderRadius: 999,
                  marginTop: current ? 6 : 8,
                  background: current ? 'var(--accent)' : pct <= progress ? '#ffcc55' : 'var(--bg-3)',
                  border: current ? '2px solid var(--bg)' : pct <= progress ? 'none' : '1px solid var(--line-2)',
                  boxShadow: current ? '0 0 0 3px rgba(255,170,0,0.2)' : 'none',
                }} />
              </div>
            )
          })}
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 2, fontSize: 10.5, color: 'var(--text-3)', fontFamily: 'var(--mono)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
          {phases.map(p => <span key={p} style={{ width: '16.6%', textAlign: 'center' }}>{p}</span>)}
        </div>
      </Card>

      {/* KPIs */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 14, marginBottom: 20 }}>
        <KPI
          label="Open findings"
          value={open}
          delta={open > 0 ? `+${open}` : '0'}
          deltaLabel="requiring attention"
          spark={<Sparkline data={sparkData} color="var(--accent)" fill="rgba(255,170,0,0.12)" width={200} height={30} />}
          icon={<Ic name="bug" size={14} />}
        />
        <KPI
          label="Critical · unresolved"
          value={counts.critical}
          color={counts.critical > 0 ? 'var(--crit)' : undefined}
          deltaLabel={counts.critical > 0 ? 'immediate action required' : 'none found — good'}
          spark={<Sparkline data={[0, 0, counts.critical]} color="var(--crit)" fill="rgba(255,74,94,0.15)" width={200} height={30} />}
          icon={<Ic name="zap" size={14} />}
        />
        <KPI
          label="Scan runs"
          value={runs.length}
          deltaLabel={`${runs.filter(r => r.status === 'running').length} running · ${runs.filter(r => r.status === 'completed').length} done`}
          icon={<Ic name="terminal" size={14} />}
        />
        <KPI
          label="Resolved"
          value={resolved}
          color="var(--ok)"
          deltaLabel={total > 0 ? `${Math.round((resolved / total) * 100)}% of total` : 'no findings yet'}
          icon={<Ic name="check" size={14} />}
        />
      </div>

      {/* Severity breakdown + risk */}
      <div style={{ display: 'grid', gridTemplateColumns: '1.1fr 1fr', gap: 14, marginBottom: 20 }}>
        <Card>
          <SectionHeader
            title="Findings by severity"
            subtitle="Open findings across the current engagement"
            right={<Button variant="ghost" size="sm" iconRight={<Ic name="chevRight" size={12} />} onClick={() => onNav('findings')}>All findings</Button>}
          />
          {findingsLoading ? <div style={{ display: 'flex', justifyContent: 'center', padding: 24 }}><Spinner /></div> : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {(['critical', 'high', 'medium', 'low', 'info'] as const).map(sev => {
                const val = counts[sev]
                const max = Math.max(...Object.values(counts), 1)
                return (
                  <div key={sev} style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                    <div style={{ width: 72 }}><SevPill sev={sev} /></div>
                    <div style={{ flex: 1, height: 22, background: 'var(--bg-2)', borderRadius: 4, overflow: 'hidden', position: 'relative' }}>
                      <div style={{
                        width: `${Math.max(val / max, val > 0 ? 0.02 : 0) * 100}%`, height: '100%',
                        background: `linear-gradient(90deg, ${{ critical: '#ff4a5e', high: '#ff8847', medium: '#ffc53d', low: '#4ea8ff', info: '#7a828f' }[sev]}aa, ${{ critical: '#ff4a5e', high: '#ff8847', medium: '#ffc53d', low: '#4ea8ff', info: '#7a828f' }[sev]}44)`,
                      }} />
                      <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', padding: '0 10px', fontSize: 11.5, fontFamily: 'var(--mono)', color: val > 0 ? 'var(--text)' : 'var(--text-3)', fontWeight: 500 }}>
                        {val} {val === 1 ? 'finding' : 'findings'}
                      </div>
                    </div>
                    <div style={{ width: 48, textAlign: 'right', fontSize: 11, color: 'var(--text-3)', fontFamily: 'var(--mono)' }}>
                      {total > 0 && val > 0 ? `${Math.round((val / total) * 100)}%` : '—'}
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </Card>

        {/* Risk gauge */}
        <Card>
          <SectionHeader title="Risk overview" subtitle="By finding status" />
          <div style={{ display: 'flex', alignItems: 'center', gap: 20 }}>
            <div style={{ position: 'relative', width: 130, height: 130 }}>
              <svg viewBox="0 0 100 100" style={{ width: '100%', height: '100%', transform: 'rotate(-90deg)' }}>
                <circle cx="50" cy="50" r="42" stroke="var(--bg-3)" strokeWidth="8" fill="none" />
                {total > 0 && (
                  <circle cx="50" cy="50" r="42" stroke="url(#riskGrad)" strokeWidth="8" fill="none"
                    strokeDasharray={`${Math.PI * 2 * 42 * Math.min(1, (counts.critical * 5 + counts.high * 4 + counts.medium * 3) / (total * 5))} ${Math.PI * 2 * 42}`}
                    strokeLinecap="round" />
                )}
                <defs>
                  <linearGradient id="riskGrad" x1="0" y1="0" x2="1" y2="1">
                    <stop offset="0" stopColor="var(--high)" />
                    <stop offset="1" stopColor="var(--crit)" />
                  </linearGradient>
                </defs>
              </svg>
              <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
                <div style={{ fontSize: 30, fontWeight: 600, letterSpacing: '-0.03em', fontFamily: 'var(--mono)' }}>{total}</div>
                <div style={{ fontSize: 10, color: 'var(--text-3)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>findings</div>
              </div>
            </div>
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 10 }}>
              {[
                { label: 'Open', val: findings.filter(f => f.status === 'open').length, color: 'var(--high)' },
                { label: 'Triaged', val: findings.filter(f => f.status === 'triaged').length, color: 'var(--low)' },
                { label: 'Accepted', val: findings.filter(f => f.status === 'accepted-risk').length, color: 'var(--text-3)' },
                { label: 'Resolved', val: resolved, color: 'var(--ok)' },
              ].map(r => (
                <div key={r.label}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11.5, marginBottom: 3 }}>
                    <span style={{ color: 'var(--text-2)' }}>{r.label}</span>
                    <span style={{ color: 'var(--text-3)', fontFamily: 'var(--mono)' }}>{r.val}</span>
                  </div>
                  <Progress value={total > 0 ? r.val / total : 0} color={r.color} height={3} />
                </div>
              ))}
            </div>
          </div>
        </Card>
      </div>

      {/* Recent findings */}
      <Card padding={0} style={{ marginBottom: 20 }}>
        <div style={{ padding: '14px 16px 10px', display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between' }}>
          <div>
            <div style={{ fontSize: 14, fontWeight: 600 }}>Recent findings</div>
            <div style={{ fontSize: 12, color: 'var(--text-3)', marginTop: 2 }}>Latest across this engagement</div>
          </div>
          <Button variant="ghost" size="sm" iconRight={<Ic name="chevRight" size={12} />} onClick={() => onNav('findings')}>View all</Button>
        </div>
        {findingsLoading ? (
          <div style={{ display: 'flex', justifyContent: 'center', padding: 24 }}><Spinner /></div>
        ) : findings.length === 0 ? (
          <EmptyState icon="bug" title="No findings yet" body="Run a scan or add a finding manually." />
        ) : (
          <div>
            {findings.slice(0, 8).map(f => (
              <div key={f.id} onClick={() => onNav('findings')} style={{
                display: 'grid', gridTemplateColumns: '68px 1fr 120px 90px 30px',
                gap: 12, alignItems: 'center',
                padding: '10px 16px',
                borderTop: '1px solid var(--line)',
                cursor: 'pointer',
              }} className="hover-row">
                <SevPill sev={f.severity} compact />
                <div style={{ minWidth: 0 }}>
                  <div style={{ fontSize: 13, fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{f.title}</div>
                  <div style={{ fontSize: 11, color: 'var(--text-3)', fontFamily: 'var(--mono)', marginTop: 2 }}>
                    {f.target || '—'} · {new Date(f.created_at).toLocaleDateString()}
                  </div>
                </div>
                <StatusPill status={f.status} />
                <div style={{ fontSize: 11.5, color: 'var(--text-3)' }}>
                  {new Date(f.updated_at).toLocaleDateString()}
                </div>
                {f.assignee_id && <Avatar id={f.assignee_id} size={22} />}
              </div>
            ))}
          </div>
        )}
      </Card>

      {/* All engagements */}
      <div style={{ marginBottom: 24 }}>
        <SectionHeader
          title="All engagements"
          subtitle="Across your workspace"
          right={
            <Button variant="secondary" size="sm" icon={<Ic name="plus" size={13} />} onClick={() => onNav('new-engagement')}>
              New engagement
            </Button>
          }
        />
        {engagements.length === 0 ? (
          <EmptyState icon="folder" title="No engagements" body="Create your first engagement to get started." />
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: 12 }}>
            {engagements.map(e => (
              <Card key={e.id} padding={0} style={{ overflow: 'hidden' }} hover>
                <div style={{ padding: '14px 14px 10px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6 }}>
                    <span style={{ fontSize: 10, fontFamily: 'var(--mono)', color: 'var(--text-3)', padding: '1px 5px', background: 'var(--bg-3)', borderRadius: 3, textTransform: 'uppercase' }}>
                      {e.engagement_type || 'pentest'}
                    </span>
                    <span style={{ fontSize: 10.5, color: e.status === 'active' ? 'var(--ok)' : 'var(--text-3)', display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                      <span style={{ width: 6, height: 6, borderRadius: 999, background: e.status === 'active' ? 'var(--ok)' : 'var(--text-3)' }} />
                      {e.status}
                    </span>
                  </div>
                  <div style={{ fontSize: 13.5, fontWeight: 500, marginBottom: 3 }}>{e.client_name || e.name}</div>
                  <div style={{ fontSize: 11.5, color: 'var(--text-3)', marginBottom: 10 }}>{e.name}</div>
                  <Progress value={e.status === 'completed' ? 1 : e.status === 'active' ? 0.5 : 0.1} color={e.status === 'paused' ? 'var(--text-3)' : 'var(--accent)'} height={3} />
                </div>
                <div style={{ padding: '8px 14px', borderTop: '1px solid var(--line)', fontSize: 11, color: 'var(--text-3)' }}>
                  {e.end_date ? `Due ${new Date(e.end_date).toLocaleDateString()}` : 'No deadline set'}
                </div>
              </Card>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

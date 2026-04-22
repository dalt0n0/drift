import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { Ic } from '../components/Icon'
import { Button, Card, EmptyState, FieldRow, Input, SectionHeader, Spinner, Tag } from '../components/primitives'
import { getMe, getSbomSummary, getUsers } from '../api'

export default function Settings() {
  const navigate = useNavigate()
  const [tab, setTab] = useState<'general' | 'sbom' | 'team'>('general')
  const { data: user } = useQuery({ queryKey: ['me'], queryFn: getMe })
  const { data: sbom } = useQuery({ queryKey: ['sbom'], queryFn: getSbomSummary })
  const { data: users = [], isLoading: usersLoading } = useQuery({
    queryKey: ['users'], queryFn: getUsers, enabled: tab === 'team',
  })

  const tabs = [
    { id: 'general' as const, label: 'General', icon: 'settings' },
    { id: 'sbom' as const, label: 'SBOM', icon: 'shield' },
    { id: 'team' as const, label: 'Team', icon: 'users' },
  ]

  return (
    <div style={{ display: 'flex', height: 'calc(100vh - 46px)' }}>
      {/* Sidebar tabs */}
      <div style={{ width: 200, borderRight: '1px solid var(--line)', padding: '14px 10px', display: 'flex', flexDirection: 'column', gap: 2 }}>
        {tabs.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)} style={{
            display: 'flex', alignItems: 'center', gap: 9,
            padding: '7px 10px', borderRadius: 6, fontSize: 13,
            background: tab === t.id ? 'var(--bg-3)' : 'transparent',
            color: tab === t.id ? 'var(--text)' : 'var(--text-2)',
            fontWeight: tab === t.id ? 500 : 400,
          }}>
            <Ic name={t.icon} size={14} /> {t.label}
          </button>
        ))}
      </div>

      <div style={{ flex: 1, overflow: 'auto', padding: '24px 32px', maxWidth: 720 }}>
        {tab === 'general' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
            <SectionHeader title="General settings" subtitle="Configure your workspace preferences" />
            <Card>
              <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 14 }}>Profile</div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                <FieldRow label="Username">
                  <Input value={user?.username || ''} onChange={() => {}} disabled />
                </FieldRow>
                <FieldRow label="Full name">
                  <Input value={user?.full_name || ''} onChange={() => {}} disabled />
                </FieldRow>
                <FieldRow label="Email">
                  <Input value={user?.email || ''} onChange={() => {}} disabled />
                </FieldRow>
                <FieldRow label="Role">
                  <div style={{ padding: '6px 10px', background: 'var(--bg-2)', borderRadius: 6, fontSize: 13, fontFamily: 'var(--mono)' }}>
                    {user?.role || '—'}
                  </div>
                </FieldRow>
              </div>
            </Card>

            <Card>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div>
                  <div style={{ fontSize: 13, fontWeight: 600 }}>Password</div>
                  <div style={{ fontSize: 12, color: 'var(--text-3)', marginTop: 4 }}>Change the password used to sign in.</div>
                </div>
                <Button variant="secondary" icon={<Ic name="key" size={13} />} onClick={() => navigate('/change-password')}>
                  Change password
                </Button>
              </div>
            </Card>
          </div>
        )}

        {tab === 'sbom' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
            <SectionHeader title="Software Bill of Materials" subtitle="Supply chain transparency for Drift" />
            <Card>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div style={{ fontSize: 13, fontWeight: 600 }}>SBOM summary</div>
                  <Tag tone="ok">CycloneDX 1.5 + SPDX 2.3</Tag>
                </div>
                {sbom ? (
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                    {[
                      { label: 'App version', value: sbom.app_version },
                      { label: 'Components', value: sbom.component_count },
                      { label: 'Format', value: sbom.bom_format },
                      { label: 'Spec version', value: sbom.spec_version },
                    ].map(r => (
                      <div key={r.label} style={{ padding: 12, background: 'var(--bg-2)', borderRadius: 6 }}>
                        <div style={{ fontSize: 11, color: 'var(--text-3)', marginBottom: 4 }}>{r.label}</div>
                        <div style={{ fontFamily: 'var(--mono)', fontSize: 13 }}>{String(r.value)}</div>
                      </div>
                    ))}
                  </div>
                ) : <Spinner />}
                <div style={{ display: 'flex', gap: 8, marginTop: 4 }}>
                  <Button variant="secondary" size="sm" icon={<Ic name="download" size={13} />}
                    onClick={() => window.open('/api/sbom?format=cyclonedx', '_blank')}>
                    Download CycloneDX
                  </Button>
                  <Button variant="secondary" size="sm" icon={<Ic name="download" size={13} />}
                    onClick={() => window.open('/api/sbom?format=spdx', '_blank')}>
                    Download SPDX
                  </Button>
                </div>
              </div>
            </Card>
            <Card>
              <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 10 }}>Cosign verification</div>
              <div style={{ fontFamily: 'var(--mono)', fontSize: 12, color: 'var(--text-2)', lineHeight: 1.7, padding: '10px 14px', background: 'var(--bg-2)', borderRadius: 6 }}>
                cosign verify ghcr.io/dalt0n0/drift/api:v0.1.0 \<br />
                {'  '}--certificate-identity-regexp="https://github.com/dalt0n0/drift" \<br />
                {'  '}--certificate-oidc-issuer="https://token.actions.githubusercontent.com"
              </div>
            </Card>
          </div>
        )}

        {tab === 'team' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
            <SectionHeader title="Team members" subtitle="All users with access to this workspace" />
            {usersLoading ? (
              <div style={{ display: 'flex', justifyContent: 'center', padding: 32 }}><Spinner /></div>
            ) : users.length === 0 ? (
              <EmptyState icon="users" title="No users" body="Add users via the API or admin CLI." />
            ) : (
              <Card padding={0}>
                {users.map(u => (
                  <div key={u.id} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '12px 16px', borderBottom: '1px solid var(--line)' }}>
                    <div style={{ width: 32, height: 32, borderRadius: 999, background: 'var(--accent-bg)', color: 'var(--accent)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontFamily: 'var(--mono)', fontSize: 12, fontWeight: 600, border: '1px solid var(--accent-line)' }}>
                      {u.username.slice(0, 2).toUpperCase()}
                    </div>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: 13, fontWeight: 500 }}>{u.full_name || u.username}</div>
                      <div style={{ fontSize: 12, color: 'var(--text-3)', fontFamily: 'var(--mono)' }}>{u.username} · {u.email}</div>
                    </div>
                    <Tag tone={u.role === 'admin' ? 'accent' : 'neutral'}>{u.role}</Tag>
                    <div style={{ width: 7, height: 7, borderRadius: 999, background: u.is_active ? 'var(--ok)' : 'var(--text-4)' }} title={u.is_active ? 'Active' : 'Inactive'} />
                  </div>
                ))}
              </Card>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

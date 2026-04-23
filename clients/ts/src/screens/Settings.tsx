import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { Ic } from '../components/Icon'
import { Button, Card, EmptyState, FieldRow, Input, Modal, Select, SectionHeader, Spinner, Tag } from '../components/primitives'
import { getMe, getSbomSummary, getUsers, createUser, updateUser, deleteUser } from '../api'
import type { Role, User } from '../types'

const ELEVATED_ROLES: Role[] = ['lead', 'operator', 'admin']

function NewUserModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const qc = useQueryClient()
  const [username, setUsername] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [fullName, setFullName] = useState('')
  const [role, setRole] = useState('tester')
  const [mustChange, setMustChange] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const reset = () => {
    setUsername(''); setEmail(''); setPassword(''); setFullName('')
    setRole('tester'); setMustChange(true); setError(null)
  }

  const mutation = useMutation({
    mutationFn: () => createUser({
      username: username.trim(),
      email: email.trim(),
      password,
      full_name: fullName.trim() || undefined,
      role,
      must_change_password: mustChange,
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['users'] })
      reset()
      onClose()
    },
    onError: (err: any) => {
      const detail = err?.response?.data?.detail
      setError(typeof detail === 'string' ? detail : JSON.stringify(detail) || 'Failed to create user')
    },
  })

  const submit = () => {
    setError(null)
    if (!username.trim()) { setError('Username is required'); return }
    if (!email.trim()) { setError('Email is required'); return }
    if (!password) { setError('Password is required'); return }
    mutation.mutate()
  }

  return (
    <Modal open={open} onClose={() => { reset(); onClose() }} title="New user" width={480}>
      <div style={{ padding: 18, display: 'flex', flexDirection: 'column', gap: 14 }}>
        <FieldRow label="Username *">
          <Input value={username} onChange={setUsername} placeholder="jdoe" autoFocus />
        </FieldRow>
        <FieldRow label="Email *">
          <Input value={email} onChange={setEmail} placeholder="jdoe@example.com" type="email" />
        </FieldRow>
        <FieldRow label="Password *">
          <Input value={password} onChange={setPassword} placeholder="Temporary password" type="password" />
        </FieldRow>
        <FieldRow label="Full name">
          <Input value={fullName} onChange={setFullName} placeholder="Jane Doe" />
        </FieldRow>
        <FieldRow label="Role">
          <Select value={role} onChange={setRole}>
            {['viewer', 'tester', 'lead', 'operator', 'admin'].map(r => (
              <option key={r} value={r}>{r.charAt(0).toUpperCase() + r.slice(1)}</option>
            ))}
          </Select>
        </FieldRow>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <input
            type="checkbox"
            id="must-change"
            checked={mustChange}
            onChange={e => setMustChange(e.target.checked)}
            style={{ width: 16, height: 16, cursor: 'pointer' }}
          />
          <label htmlFor="must-change" style={{ fontSize: 13, color: 'var(--text-2)', cursor: 'pointer' }}>
            Require password change on first login
          </label>
        </div>
        {error && (
          <div style={{ padding: '8px 10px', background: 'rgba(255,74,94,0.08)', border: '1px solid rgba(255,74,94,0.3)', borderRadius: 6, color: '#ff8a99', fontSize: 12 }}>
            {error}
          </div>
        )}
        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 4 }}>
          <Button variant="ghost" onClick={() => { reset(); onClose() }} disabled={mutation.isPending}>Cancel</Button>
          <Button variant="primary" onClick={submit} disabled={mutation.isPending}>
            {mutation.isPending ? 'Creating…' : 'Create user'}
          </Button>
        </div>
      </div>
    </Modal>
  )
}

function EditUserModal({ user: target, onClose, isAdmin }: { user: User; onClose: () => void; isAdmin: boolean }) {
  const qc = useQueryClient()
  const [fullName, setFullName] = useState(target.full_name || '')
  const [email, setEmail] = useState(target.email || '')
  const [role, setRole] = useState(target.role || 'viewer')
  const [isActive, setIsActive] = useState(target.is_active)
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)

  const mutation = useMutation({
    mutationFn: () => updateUser(target.id, {
      full_name: fullName.trim() || undefined,
      email: email.trim() || undefined,
      role: isAdmin ? role : undefined,
      is_active: isAdmin ? isActive : undefined,
      password: isAdmin && password ? password : undefined,
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['users'] })
      onClose()
    },
    onError: (err: any) => {
      const detail = err?.response?.data?.detail
      setError(typeof detail === 'string' ? detail : 'Failed to update user')
    },
  })

  return (
    <Modal open onClose={onClose} title={`Edit ${target.username}`} width={480}>
      <div style={{ padding: 18, display: 'flex', flexDirection: 'column', gap: 14 }}>
        <FieldRow label="Full name">
          <Input value={fullName} onChange={setFullName} placeholder="Jane Doe" autoFocus />
        </FieldRow>
        <FieldRow label="Email">
          <Input value={email} onChange={setEmail} placeholder="user@example.com" type="email" />
        </FieldRow>
        {isAdmin && (
          <>
            <FieldRow label="Role">
              <Select value={role} onChange={setRole}>
                {['viewer', 'tester', 'lead', 'operator', 'admin'].map(r => (
                  <option key={r} value={r}>{r.charAt(0).toUpperCase() + r.slice(1)}</option>
                ))}
              </Select>
            </FieldRow>
            <FieldRow label="Set password">
              <Input value={password} onChange={setPassword} placeholder="Leave blank to keep current" type="password" />
            </FieldRow>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <input
                type="checkbox"
                id="is-active"
                checked={isActive}
                onChange={e => setIsActive(e.target.checked)}
                style={{ width: 16, height: 16, cursor: 'pointer' }}
              />
              <label htmlFor="is-active" style={{ fontSize: 13, color: 'var(--text-2)', cursor: 'pointer' }}>
                Account active
              </label>
            </div>
          </>
        )}
        {error && (
          <div style={{ padding: '8px 10px', background: 'rgba(255,74,94,0.08)', border: '1px solid rgba(255,74,94,0.3)', borderRadius: 6, color: '#ff8a99', fontSize: 12 }}>
            {error}
          </div>
        )}
        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 4 }}>
          <Button variant="ghost" onClick={onClose} disabled={mutation.isPending}>Cancel</Button>
          <Button variant="primary" onClick={() => mutation.mutate()} disabled={mutation.isPending}>
            {mutation.isPending ? 'Saving…' : 'Save'}
          </Button>
        </div>
      </div>
    </Modal>
  )
}

export default function Settings() {
  const navigate = useNavigate()
  const qc = useQueryClient()
  const [tab, setTab] = useState<'general' | 'sbom' | 'team'>('general')
  const [newUserOpen, setNewUserOpen] = useState(false)
  const [editUser, setEditUser] = useState<User | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<User | null>(null)
  const { data: user } = useQuery({ queryKey: ['me'], queryFn: getMe })
  const { data: sbom } = useQuery({ queryKey: ['sbom'], queryFn: getSbomSummary })
  const { data: users = [], isLoading: usersLoading } = useQuery({
    queryKey: ['users'], queryFn: getUsers, enabled: tab === 'team',
  })

  const delMutation = useMutation({
    mutationFn: (userId: string) => deleteUser(userId),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['users'] }); setDeleteTarget(null) },
  })

  const hasTeamAccess = user && ELEVATED_ROLES.includes(user.role as Role)

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
            <SectionHeader
              title="Team members"
              subtitle="All users with access to this workspace"
              right={
                hasTeamAccess ? (
                  <Button variant="primary" size="sm" icon={<Ic name="plus" size={13} />} onClick={() => setNewUserOpen(true)}>
                    New user
                  </Button>
                ) : undefined
              }
            />
            {!hasTeamAccess ? (
              <Card>
                <div style={{ fontSize: 13, color: 'var(--text-3)' }}>
                  You need lead or higher role to manage users.
                </div>
              </Card>
            ) : usersLoading ? (
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
                    {user?.role === 'admin' && (
                      <div style={{ display: 'flex', gap: 4 }}>
                        <IconButton icon={<Ic name="edit" size={13} />} size={24} onClick={() => setEditUser(u)} title="Edit user" />
                        {u.id !== user.id && (
                          deleteTarget?.id === u.id ? (
                            <div style={{ display: 'flex', gap: 4 }}>
                              <button onClick={() => delMutation.mutate(u.id)} disabled={delMutation.isPending} style={{ padding: '2px 8px', borderRadius: 4, fontSize: 11, background: 'rgba(255,74,94,0.15)', color: 'var(--crit)', cursor: 'pointer' }}>
                                {delMutation.isPending ? '…' : 'Confirm'}
                              </button>
                              <button onClick={() => setDeleteTarget(null)} style={{ padding: '2px 8px', borderRadius: 4, fontSize: 11, background: 'var(--bg-3)', color: 'var(--text-2)', cursor: 'pointer' }}>
                                Cancel
                              </button>
                            </div>
                          ) : (
                            <IconButton icon={<Ic name="trash" size={13} />} size={24} onClick={() => setDeleteTarget(u)} title="Delete user" style={{ color: 'var(--crit)' }} />
                          )
                        )}
                      </div>
                    )}
                  </div>
                ))}
              </Card>
            )}
          </div>
        )}
      </div>
      <NewUserModal open={newUserOpen} onClose={() => setNewUserOpen(false)} />
      {editUser && (
        <EditUserModal
          user={editUser}
          onClose={() => setEditUser(null)}
          isAdmin={user?.role === 'admin'}
        />
      )}
    </div>
  )
}

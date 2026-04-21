import { useState } from 'react'
import { Ic } from '../components/Icon'
import { Button, Card, EmptyState, FieldRow, IconButton, Input, Modal, Select, Tag } from '../components/primitives'
import type { Engagement } from '../types'

interface Props { engagement: Engagement | null }

interface Credential {
  id: string
  label: string
  type: 'password' | 'ssh-key' | 'api-key' | 'token' | 'certificate'
  username?: string
  secret: string
  target?: string
  notes?: string
  addedAt: string
  revealed: boolean
}

const CRED_TYPES = ['password', 'ssh-key', 'api-key', 'token', 'certificate'] as const

const typeIcons: Record<string, string> = {
  password: 'lock', 'ssh-key': 'key', 'api-key': 'code', token: 'zap', certificate: 'shield',
}

const typeColors: Record<string, string> = {
  password: '#ff8847', 'ssh-key': '#4ea8ff', 'api-key': '#ffaa00', token: '#34d399', certificate: '#c084fc',
}

function AddCredModal({ open, onClose, onAdd }: { open: boolean; onClose: () => void; onAdd: (c: Omit<Credential, 'id' | 'addedAt' | 'revealed'>) => void }) {
  const [label, setLabel] = useState('')
  const [type, setType] = useState<Credential['type']>('password')
  const [username, setUsername] = useState('')
  const [secret, setSecret] = useState('')
  const [target, setTarget] = useState('')
  const [notes, setNotes] = useState('')
  const [showSecret, setShowSecret] = useState(false)

  const submit = () => {
    if (!label || !secret) return
    onAdd({ label, type, username, secret, target, notes })
    setLabel(''); setUsername(''); setSecret(''); setTarget(''); setNotes('')
    onClose()
  }

  return (
    <Modal open={open} onClose={onClose} title="Add credential" width={480}>
      <div style={{ padding: 20, display: 'flex', flexDirection: 'column', gap: 14 }}>
        <FieldRow label="Label *"><Input value={label} onChange={setLabel} placeholder="Admin panel login" /></FieldRow>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
          <FieldRow label="Type">
            <Select value={type} onChange={v => setType(v as Credential['type'])}>
              {CRED_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
            </Select>
          </FieldRow>
          <FieldRow label="Target"><Input value={target} onChange={setTarget} placeholder="admin.example.com" /></FieldRow>
          {(type === 'password') && <FieldRow label="Username"><Input value={username} onChange={setUsername} placeholder="admin" /></FieldRow>}
        </div>
        <FieldRow label="Secret *">
          <div style={{ position: 'relative' }}>
            <Input value={secret} onChange={setSecret} type={showSecret ? 'text' : 'password'} placeholder="••••••••" />
            <button onClick={() => setShowSecret(!showSecret)} style={{ position: 'absolute', right: 8, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-3)' }}>
              <Ic name={showSecret ? 'eyeOff' : 'eye'} size={14} />
            </button>
          </div>
        </FieldRow>
        <FieldRow label="Notes"><Input value={notes} onChange={setNotes} placeholder="Found via credential stuffing, portal login" /></FieldRow>
        <div style={{ padding: '8px 12px', background: 'rgba(255,170,0,0.08)', border: '1px solid var(--accent-line)', borderRadius: 6, fontSize: 12, color: 'var(--text-3)', display: 'flex', gap: 8 }}>
          <Ic name="lock" size={13} style={{ color: 'var(--accent)', flexShrink: 0, marginTop: 1 }} />
          Credentials are stored encrypted at rest. Access is audit-logged.
        </div>
        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button variant="primary" onClick={submit} disabled={!label || !secret}>Add credential</Button>
        </div>
      </div>
    </Modal>
  )
}

export default function Vault({ engagement }: Props) {
  const [creds, setCreds] = useState<Credential[]>([
    { id: '1', label: 'Admin panel login', type: 'password', username: 'admin', secret: 'P@ssw0rd123!', target: 'admin.example.com', notes: 'Found via credential stuffing', addedAt: new Date().toISOString(), revealed: false },
    { id: '2', label: 'API key (dev env)', type: 'api-key', secret: 'sk-test-abc123xyz', target: 'api.example.com', addedAt: new Date().toISOString(), revealed: false },
  ])
  const [selectedId, setSelectedId] = useState<string | null>(creds[0]?.id || null)
  const [addOpen, setAddOpen] = useState(false)
  const [search, setSearch] = useState('')
  const [typeFilter, setTypeFilter] = useState('all')

  const selected = creds.find(c => c.id === selectedId) || null

  const addCred = (data: Omit<Credential, 'id' | 'addedAt' | 'revealed'>) => {
    setCreds(prev => [...prev, { ...data, id: String(Date.now()), addedAt: new Date().toISOString(), revealed: false }])
  }

  const toggleReveal = (id: string) => {
    setCreds(prev => prev.map(c => c.id === id ? { ...c, revealed: !c.revealed } : c))
  }

  const deleteCred = (id: string) => {
    setCreds(prev => prev.filter(c => c.id !== id))
    if (selectedId === id) setSelectedId(null)
  }

  const filtered = creds.filter(c =>
    (typeFilter === 'all' || c.type === typeFilter) &&
    (!search || c.label.toLowerCase().includes(search.toLowerCase()) || c.target?.includes(search))
  )

  if (!engagement) return <EmptyState icon="key" title="No engagement selected" />

  return (
    <div style={{ display: 'flex', height: 'calc(100vh - 46px)' }}>
      {/* List */}
      <div style={{ width: 340, flexShrink: 0, borderRight: '1px solid var(--line)', display: 'flex', flexDirection: 'column', background: 'var(--bg-1)' }}>
        <div style={{ padding: '12px 14px', borderBottom: '1px solid var(--line)' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
            <div>
              <div style={{ fontSize: 14, fontWeight: 600 }}>Vault</div>
              <div style={{ fontSize: 11, color: 'var(--text-3)', marginTop: 2, display: 'flex', alignItems: 'center', gap: 5 }}>
                <Ic name="lock" size={11} /> AES-256 encrypted
              </div>
            </div>
            <Button variant="primary" size="sm" icon={<Ic name="plus" size={13} />} onClick={() => setAddOpen(true)}>Add</Button>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '5px 9px', height: 28, background: 'var(--bg-2)', border: '1px solid var(--line)', borderRadius: 6, color: 'var(--text-3)', fontSize: 12 }}>
            <Ic name="search" size={13} />
            <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search vault…" style={{ flex: 1, background: 'none', fontSize: 12, color: 'var(--text)' }} />
          </div>
          <div style={{ display: 'flex', gap: 2, marginTop: 8 }}>
            {['all', ...CRED_TYPES].map(t => (
              <button key={t} onClick={() => setTypeFilter(t)} style={{
                padding: '2px 7px', fontSize: 11, borderRadius: 4, textTransform: 'capitalize',
                background: typeFilter === t ? 'var(--bg-3)' : 'transparent',
                color: typeFilter === t ? 'var(--text)' : 'var(--text-3)',
              }}>{t}</button>
            ))}
          </div>
        </div>
        <div style={{ flex: 1, overflow: 'auto' }}>
          {filtered.length === 0 ? (
            <EmptyState icon="key" title="No credentials" body="Add credentials captured during the engagement." />
          ) : filtered.map(c => (
            <div key={c.id} onClick={() => setSelectedId(c.id)} className="hover-row" style={{
              padding: '10px 14px', borderBottom: '1px solid var(--line)', cursor: 'pointer',
              background: selectedId === c.id ? 'var(--bg-2)' : 'transparent',
              borderLeft: selectedId === c.id ? '2px solid var(--accent)' : '2px solid transparent',
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                <div style={{
                  width: 22, height: 22, borderRadius: 5, flexShrink: 0,
                  background: `${typeColors[c.type] || '#7a828f'}18`,
                  color: typeColors[c.type] || '#7a828f',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                }}>
                  <Ic name={typeIcons[c.type] || 'key'} size={12} />
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 13, fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{c.label}</div>
                  <div style={{ fontSize: 11, color: 'var(--text-3)', fontFamily: 'var(--mono)' }}>{c.type}{c.target ? ` · ${c.target}` : ''}</div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Detail */}
      <div style={{ flex: 1, minWidth: 0, background: 'var(--bg)', overflow: 'auto' }}>
        {selected ? (
          <div style={{ padding: '20px 24px' }}>
            <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 20 }}>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6 }}>
                  <div style={{
                    width: 32, height: 32, borderRadius: 8,
                    background: `${typeColors[selected.type] || '#7a828f'}18`,
                    color: typeColors[selected.type] || '#7a828f',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                  }}>
                    <Ic name={typeIcons[selected.type] || 'key'} size={16} />
                  </div>
                  <div style={{ fontSize: 18, fontWeight: 600 }}>{selected.label}</div>
                </div>
                <div style={{ display: 'flex', gap: 10 }}>
                  <Tag>{selected.type}</Tag>
                  {selected.target && <Tag tone="neutral"><Ic name="globe" size={11} /> {selected.target}</Tag>}
                </div>
              </div>
              <Button variant="danger" size="sm" icon={<Ic name="trash" size={13} />} onClick={() => deleteCred(selected.id)}>Delete</Button>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              {selected.username && (
                <Card padding={14}>
                  <div style={{ fontSize: 11, color: 'var(--text-3)', marginBottom: 6 }}>USERNAME</div>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <span style={{ fontFamily: 'var(--mono)', fontSize: 14 }}>{selected.username}</span>
                    <IconButton icon={<Ic name="copy" size={13} />} onClick={() => navigator.clipboard.writeText(selected.username || '')} title="Copy" />
                  </div>
                </Card>
              )}

              <Card padding={14}>
                <div style={{ fontSize: 11, color: 'var(--text-3)', marginBottom: 6 }}>SECRET</div>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10 }}>
                  <span style={{ fontFamily: 'var(--mono)', fontSize: 13, letterSpacing: selected.revealed ? 'normal' : '0.15em', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1 }}>
                    {selected.revealed ? selected.secret : '•'.repeat(Math.min(selected.secret.length, 24))}
                  </span>
                  <div style={{ display: 'flex', gap: 4, flexShrink: 0 }}>
                    <IconButton icon={<Ic name={selected.revealed ? 'eyeOff' : 'eye'} size={13} />} onClick={() => toggleReveal(selected.id)} title={selected.revealed ? 'Hide' : 'Reveal'} />
                    <IconButton icon={<Ic name="copy" size={13} />} onClick={() => navigator.clipboard.writeText(selected.secret)} title="Copy" />
                  </div>
                </div>
              </Card>

              {selected.notes && (
                <Card padding={14}>
                  <div style={{ fontSize: 11, color: 'var(--text-3)', marginBottom: 6 }}>NOTES</div>
                  <div style={{ fontSize: 13, color: 'var(--text-2)', lineHeight: 1.6 }}>{selected.notes}</div>
                </Card>
              )}

              <Card padding={14}>
                <div style={{ fontSize: 11, color: 'var(--text-3)', marginBottom: 6 }}>AUDIT</div>
                <div style={{ fontSize: 12, color: 'var(--text-3)' }}>
                  Added {new Date(selected.addedAt).toLocaleString()} · Access is audit-logged
                </div>
              </Card>
            </div>
          </div>
        ) : (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%' }}>
            <EmptyState icon="key" title="Select a credential" body="Choose a credential from the vault to view details." action={
              <Button variant="primary" icon={<Ic name="plus" size={14} />} onClick={() => setAddOpen(true)}>Add first credential</Button>
            } />
          </div>
        )}
      </div>

      <AddCredModal open={addOpen} onClose={() => setAddOpen(false)} onAdd={addCred} />
    </div>
  )
}

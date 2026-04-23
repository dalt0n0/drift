import { useState, useEffect, useRef, type ReactNode } from 'react'
import { Ic } from './Icon'
import { Avatar, IconButton } from './primitives'
import type { Engagement, Organization, User } from '../types'

// ── Sidebar ───────────────────────────────────────────────────────────
const navMain = [
  { id: 'dashboard', label: 'Dashboard', icon: 'dashboard', count: null as null | number, warn: false },
  { id: 'targets',   label: 'Targets',   icon: 'target',    count: null, warn: false },
  { id: 'findings',  label: 'Findings',  icon: 'bug',       count: null, warn: true },
  { id: 'runs',      label: 'Scan runs', icon: 'terminal',  count: null, warn: false },
  { id: 'report',    label: 'Report',    icon: 'report',    count: null, warn: false },
]
const navWorkspace = [
  { id: 'audit',    label: 'Audit log',      icon: 'shield' },
  { id: 'settings', label: 'Settings',       icon: 'settings' },
]

function NavItem({ item, active, onClick, findingsCount }: {
  item: typeof navMain[0]; active: boolean; onClick: () => void; findingsCount?: number
}) {
  const [hover, setHover] = useState(false)
  const count = item.id === 'findings' ? findingsCount : item.count
  return (
    <button
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      onClick={onClick}
      style={{
        display: 'flex', alignItems: 'center', gap: 10,
        width: '100%', padding: '6px 10px', borderRadius: 6,
        background: active ? 'var(--bg-3)' : hover ? 'rgba(255,255,255,0.03)' : 'transparent',
        color: active ? 'var(--text)' : 'var(--text-2)',
        fontSize: 13, fontWeight: active ? 500 : 400,
        position: 'relative', textAlign: 'left',
      }}
    >
      {active && <div style={{ position: 'absolute', left: -10, top: 6, bottom: 6, width: 2, background: 'var(--accent)', borderRadius: 2 }} />}
      <Ic name={item.icon} size={15} />
      <span style={{ flex: 1 }}>{item.label}</span>
      {count != null && count > 0 && (
        <span style={{
          fontSize: 10.5, fontFamily: 'var(--mono)', padding: '0 5px', height: 15, lineHeight: '15px',
          borderRadius: 3,
          background: item.warn ? 'rgba(255,136,71,0.14)' : 'var(--bg-3)',
          color: item.warn ? 'var(--high)' : 'var(--text-3)',
          border: `1px solid ${item.warn ? 'rgba(255,136,71,0.28)' : 'var(--line)'}`,
        }}>{count}</span>
      )}
    </button>
  )
}

interface SidebarProps {
  current: string
  onNav: (id: string) => void
  engagement: Engagement | null
  engagements: Engagement[]
  onSwitchEngagement: (id: string) => void
  organizations: Organization[]
  selectedOrgId: string | null
  onSelectOrg: (orgId: string | null) => void
  user: User | null
  findingsCount: number
  onSignOut: () => void
}

export function Sidebar({ current, onNav, engagement, engagements, onSwitchEngagement, organizations, selectedOrgId, onSelectOrg, user, findingsCount, onSignOut }: SidebarProps) {
  const [orgOpen, setOrgOpen] = useState(false)
  const [engOpen, setEngOpen] = useState(false)
  const [userMenuOpen, setUserMenuOpen] = useState(false)
  const userMenuRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!userMenuOpen) return
    const onDocClick = (e: MouseEvent) => {
      if (userMenuRef.current && !userMenuRef.current.contains(e.target as Node)) {
        setUserMenuOpen(false)
      }
    }
    document.addEventListener('mousedown', onDocClick)
    return () => document.removeEventListener('mousedown', onDocClick)
  }, [userMenuOpen])

  const selectedOrg = organizations.find(o => o.id === selectedOrgId) || null
  const orgInitials = selectedOrg?.name?.slice(0, 2).toUpperCase() || 'AL'
  const engInitials = engagement?.title?.slice(0, 2).toUpperCase() || '??'

  return (
    <aside style={{
      width: 232, flexShrink: 0,
      background: 'var(--bg-1)',
      borderRight: '1px solid var(--line)',
      display: 'flex', flexDirection: 'column',
      height: '100vh', position: 'sticky', top: 0,
      overflow: 'hidden',
    }}>
      {/* Brand */}
      <div style={{ padding: '14px 14px 8px', display: 'flex', alignItems: 'center', gap: 9 }}>
        <div style={{
          width: 22, height: 22, borderRadius: 5,
          background: 'linear-gradient(135deg, var(--accent), #ff7a00)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          boxShadow: 'inset 0 0 0 1px rgba(0,0,0,0.2)',
        }}>
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none">
            <path d="M12 2 L20 6 V12 C20 17 16 21 12 22 C8 21 4 17 4 12 V6 Z" stroke="#1a1300" strokeWidth="2.2" strokeLinejoin="round" />
            <path d="M9 12 L11 14 L15 10" stroke="#1a1300" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </div>
        <div style={{ lineHeight: 1.1 }}>
          <div style={{ fontSize: 13.5, fontWeight: 600, letterSpacing: '-0.01em' }}>Drift</div>
          <div style={{ fontSize: 10.5, color: 'var(--text-3)', fontFamily: 'var(--mono)' }}>pentest · self-hosted</div>
        </div>
      </div>

      {/* Organization switcher */}
      <div style={{ padding: '10px 10px 0', position: 'relative' }}>
        <button
          onClick={() => { setOrgOpen(!orgOpen); setEngOpen(false) }}
          style={{
            width: '100%', textAlign: 'left', padding: '8px 10px',
            background: 'var(--bg-2)', border: '1px solid var(--line)',
            borderRadius: 8, display: 'flex', alignItems: 'center', gap: 9,
          }}
        >
          <div style={{
            width: 22, height: 22, borderRadius: 5,
            background: 'var(--accent-bg)', color: 'var(--accent)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontFamily: 'var(--mono)', fontSize: 10, fontWeight: 600,
            border: '1px solid var(--accent-line)',
          }}>{orgInitials}</div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: 12.5, color: 'var(--text)', fontWeight: 500, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
              {selectedOrg?.name || 'All organizations'}
            </div>
            <div style={{ fontSize: 10.5, color: 'var(--text-3)', fontFamily: 'var(--mono)' }}>organization</div>
          </div>
          <Ic name="chevDown" size={13} />
        </button>

        {orgOpen && (
          <div style={{
            position: 'absolute', top: '100%', left: 10, right: 10, zIndex: 50,
            background: 'var(--bg-1)', border: '1px solid var(--line-2)',
            borderRadius: 8, boxShadow: 'var(--shadow-lg)', overflow: 'hidden',
            marginTop: 4,
          }}>
            <button onClick={() => { onSelectOrg(null); setOrgOpen(false) }} style={{
              width: '100%', textAlign: 'left', padding: '9px 12px',
              display: 'flex', alignItems: 'center', gap: 8,
              borderBottom: '1px solid var(--line)',
            }} className="hover-row">
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 12.5, fontWeight: 500 }}>All organizations</div>
              </div>
              {!selectedOrgId && <Ic name="check" size={13} style={{ color: 'var(--accent)' }} />}
            </button>
            {organizations.map(o => (
              <button key={o.id} onClick={() => { onSelectOrg(o.id); setOrgOpen(false) }} style={{
                width: '100%', textAlign: 'left', padding: '9px 12px',
                display: 'flex', alignItems: 'center', gap: 8,
                borderBottom: '1px solid var(--line)',
              }} className="hover-row">
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 12.5, fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{o.name}</div>
                </div>
                {o.id === selectedOrgId && <Ic name="check" size={13} style={{ color: 'var(--accent)' }} />}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Engagement switcher */}
      <div style={{ padding: '6px 10px 0', position: 'relative' }}>
        <button
          onClick={() => { setEngOpen(!engOpen); setOrgOpen(false) }}
          style={{
            width: '100%', textAlign: 'left', padding: '7px 10px',
            background: 'transparent', border: '1px solid var(--line)',
            borderRadius: 7, display: 'flex', alignItems: 'center', gap: 9,
          }}
        >
          <div style={{
            width: 20, height: 20, borderRadius: 4,
            background: 'var(--bg-3)', color: 'var(--text-2)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontFamily: 'var(--mono)', fontSize: 9, fontWeight: 600,
          }}>{engInitials}</div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: 12, color: 'var(--text-2)', fontWeight: 500, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
              {engagement?.title || 'No engagement'}
            </div>
            <div style={{ fontSize: 10, color: 'var(--text-3)', fontFamily: 'var(--mono)' }}>
              {engagement?.status || '—'}
            </div>
          </div>
          <Ic name="chevDown" size={12} />
        </button>

        {engOpen && (
          <div style={{
            position: 'absolute', top: '100%', left: 10, right: 10, zIndex: 50,
            background: 'var(--bg-1)', border: '1px solid var(--line-2)',
            borderRadius: 8, boxShadow: 'var(--shadow-lg)', overflow: 'hidden',
            marginTop: 4,
          }}>
            {engagements.map(e => (
              <button key={e.id} onClick={() => { onSwitchEngagement(e.id); setEngOpen(false) }} style={{
                width: '100%', textAlign: 'left', padding: '9px 12px',
                display: 'flex', alignItems: 'center', gap: 8,
                borderBottom: '1px solid var(--line)',
              }} className="hover-row">
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 12.5, fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {e.title}
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--text-3)', fontFamily: 'var(--mono)' }}>{e.status}</div>
                </div>
                {e.id === engagement?.id && <Ic name="check" size={13} style={{ color: 'var(--accent)' }} />}
              </button>
            ))}
            <button onClick={() => { onNav('new-engagement'); setEngOpen(false) }} style={{
              width: '100%', textAlign: 'left', padding: '9px 12px',
              display: 'flex', alignItems: 'center', gap: 8,
              color: 'var(--accent)', fontSize: 12.5,
            }} className="hover-row">
              <Ic name="plus" size={13} /> New engagement
            </button>
          </div>
        )}
      </div>

      {/* Main nav */}
      <div style={{ padding: '14px 10px 4px', display: 'flex', flexDirection: 'column', gap: 2 }}>
        {navMain.map(n => (
          <NavItem key={n.id} item={n} active={current === n.id} onClick={() => onNav(n.id)} findingsCount={findingsCount} />
        ))}
      </div>

      <div style={{ padding: '14px 18px 6px', fontSize: 10.5, color: 'var(--text-3)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
        Workspace
      </div>
      <div style={{ padding: '0 10px', display: 'flex', flexDirection: 'column', gap: 2 }}>
        {navWorkspace.map(n => (
          <NavItem key={n.id} item={{ ...n, count: null, warn: false }} active={current === n.id} onClick={() => onNav(n.id)} />
        ))}
      </div>

      <div style={{ flex: 1 }} />

      {/* User */}
      <div ref={userMenuRef} style={{ padding: '10px 12px', borderTop: '1px solid var(--line)', display: 'flex', alignItems: 'center', gap: 9, position: 'relative' }}>
        <Avatar id={user?.username || 'U'} size={26} />
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 12.5, fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {user?.full_name || user?.username || 'User'}
          </div>
          <div style={{ fontSize: 10.5, color: 'var(--text-3)', fontFamily: 'var(--mono)' }}>
            {user?.role || '—'}
          </div>
        </div>
        <IconButton icon={<Ic name="moreV" size={14} />} size={22} onClick={() => setUserMenuOpen(o => !o)} active={userMenuOpen} />
        {userMenuOpen && (
          <div style={{
            position: 'absolute', bottom: 'calc(100% - 4px)', right: 10, zIndex: 60,
            background: 'var(--bg-1)', border: '1px solid var(--line-2)',
            borderRadius: 8, boxShadow: 'var(--shadow-lg)', overflow: 'hidden',
            minWidth: 168,
          }}>
            <button onClick={() => { setUserMenuOpen(false); onNav('settings') }} style={{
              width: '100%', textAlign: 'left', padding: '9px 12px',
              display: 'flex', alignItems: 'center', gap: 8, fontSize: 12.5, color: 'var(--text)',
            }} className="hover-row">
              <Ic name="settings" size={13} /> Settings
            </button>
            <button onClick={() => { setUserMenuOpen(false); onNav('change-password') }} style={{
              width: '100%', textAlign: 'left', padding: '9px 12px',
              display: 'flex', alignItems: 'center', gap: 8, fontSize: 12.5, color: 'var(--text)',
              borderTop: '1px solid var(--line)',
            }} className="hover-row">
              <Ic name="key" size={13} /> Change password
            </button>
            <button onClick={() => { setUserMenuOpen(false); onSignOut() }} style={{
              width: '100%', textAlign: 'left', padding: '9px 12px',
              display: 'flex', alignItems: 'center', gap: 8, fontSize: 12.5, color: '#ff8a99',
              borderTop: '1px solid var(--line)',
            }} className="hover-row">
              <Ic name="logout" size={13} /> Sign out
            </button>
          </div>
        )}
      </div>
    </aside>
  )
}

// ── Topbar ────────────────────────────────────────────────────────────
interface TopbarProps {
  breadcrumbs: string[]
  right?: ReactNode
  railOpen: boolean
  onToggleRail: () => void
  notifCount?: number
}

export function Topbar({ breadcrumbs, right, railOpen, onToggleRail, notifCount = 0 }: TopbarProps) {
  return (
    <div style={{
      height: 46, flexShrink: 0,
      background: 'var(--bg)',
      borderBottom: '1px solid var(--line)',
      display: 'flex', alignItems: 'center', padding: '0 18px', gap: 14,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flex: 1, minWidth: 0 }}>
        {breadcrumbs.map((b, i) => (
          <span key={i} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            {i > 0 && <span style={{ color: 'var(--text-4)' }}>/</span>}
            <span style={{ color: i === breadcrumbs.length - 1 ? 'var(--text)' : 'var(--text-3)', fontSize: 13, fontWeight: i === breadcrumbs.length - 1 ? 500 : 400 }}>
              {b}
            </span>
          </span>
        ))}
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
        {right}
        <div style={{ position: 'relative' }}>
          <IconButton icon={<Ic name="bell" size={15} />} title="Notifications" onClick={onToggleRail} />
          {notifCount > 0 && (
            <div style={{
              position: 'absolute', top: 4, right: 4, width: 6, height: 6,
              borderRadius: 999, background: 'var(--crit)',
              border: '1.5px solid var(--bg)',
            }} />
          )}
        </div>
        <IconButton
          icon={<Ic name={railOpen ? 'close' : 'activity'} size={15} />}
          title="Activity rail"
          active={railOpen}
          onClick={onToggleRail}
        />
      </div>
    </div>
  )
}

// ── Activity Rail ─────────────────────────────────────────────────────
export function ActivityRail({ onClose }: { onClose: () => void }) {
  const [tab, setTab] = useState<'notif' | 'act'>('notif')

  return (
    <aside style={{
      width: 300, flexShrink: 0,
      background: 'var(--bg-1)', borderLeft: '1px solid var(--line)',
      display: 'flex', flexDirection: 'column',
      height: '100vh', position: 'sticky', top: 0,
    }}>
      <div style={{ padding: '12px 14px', display: 'flex', alignItems: 'center', gap: 8, borderBottom: '1px solid var(--line)' }}>
        <div style={{ display: 'flex', gap: 2, flex: 1 }}>
          {(['notif', 'act'] as const).map(t => (
            <button key={t} onClick={() => setTab(t)} style={{
              padding: '5px 10px', fontSize: 12, borderRadius: 5,
              background: tab === t ? 'var(--bg-3)' : 'transparent',
              color: tab === t ? 'var(--text)' : 'var(--text-2)',
            }}>
              {t === 'notif' ? 'Notifications' : 'Activity'}
            </button>
          ))}
        </div>
        <IconButton icon={<Ic name="close" size={14} />} size={24} onClick={onClose} />
      </div>

      <div style={{ flex: 1, overflow: 'auto' }}>
        {tab === 'notif' && (
          <div style={{ padding: '32px 16px', textAlign: 'center', color: 'var(--text-3)', fontSize: 12.5 }}>
            No notifications yet.
          </div>
        )}
        {tab === 'act' && (
          <div style={{ padding: '32px 16px', textAlign: 'center', color: 'var(--text-3)', fontSize: 12.5 }}>
            Activity from scans and findings will appear here.
          </div>
        )}
      </div>

      <div style={{ padding: '10px 14px', borderTop: '1px solid var(--line)', fontSize: 11, color: 'var(--text-3)', display: 'flex', alignItems: 'center', gap: 8 }}>
        <div style={{ width: 6, height: 6, borderRadius: 999, background: 'var(--ok)' }} />
        API connected
      </div>
    </aside>
  )
}

// ── Shell composite ───────────────────────────────────────────────────
type Screen = 'dashboard' | 'targets' | 'findings' | 'runs' | 'report' | 'vault' | 'audit' | 'settings'

const BREADCRUMBS: Record<Screen, string[]> = {
  dashboard: ['Drift', 'Dashboard'],
  targets: ['Drift', 'Targets & Scope'],
  findings: ['Drift', 'Findings'],
  runs: ['Drift', 'Scan runs'],
  report: ['Drift', 'Report'],
  vault: ['Drift', 'Vault'],
  audit: ['Drift', 'Audit log'],
  settings: ['Drift', 'Settings'],
}

interface ShellProps {
  user: User | null
  engagements: Engagement[]
  allEngagements?: Engagement[]
  organizations: Organization[]
  selectedOrgId: string | null
  onSelectOrg: (orgId: string | null) => void
  selectedEngagement: Engagement | null
  onSelectEngagement: (e: Engagement) => void
  screen: Screen
  onNav: (s: string) => void
  railOpen: boolean
  onToggleRail: () => void
  onSignOut: () => void
  children: ReactNode
  findingsCount?: number
}

export function Shell({ user, engagements, organizations, selectedOrgId, onSelectOrg, selectedEngagement, onSelectEngagement, screen, onNav, railOpen, onToggleRail, onSignOut, children, findingsCount = 0 }: ShellProps) {
  return (
    <div style={{ display: 'flex', height: '100vh', overflow: 'hidden' }}>
      <Sidebar
        current={screen}
        onNav={(id) => onNav(id as Screen)}
        engagement={selectedEngagement}
        engagements={engagements}
        onSwitchEngagement={id => {
          const e = engagements.find(e => e.id === id)
          if (e) onSelectEngagement(e)
        }}
        organizations={organizations}
        selectedOrgId={selectedOrgId}
        onSelectOrg={onSelectOrg}
        user={user}
        findingsCount={findingsCount}
        onSignOut={onSignOut}
      />
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0, overflow: 'hidden' }}>
        <Topbar
          breadcrumbs={BREADCRUMBS[screen] || ['Drift']}
          railOpen={railOpen}
          onToggleRail={onToggleRail}
        />
        <div style={{ flex: 1, overflow: 'auto' }}>
          {children}
        </div>
      </div>
      {railOpen && <ActivityRail onClose={onToggleRail} />}
    </div>
  )
}

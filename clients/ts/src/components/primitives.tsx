import { useState, type CSSProperties, type ReactNode } from 'react'
import { Ic } from './Icon'
import type { FindingSeverity, FindingStatus } from '../types'

// ── Severity meta ─────────────────────────────────────────────────────
export const sevMeta: Record<FindingSeverity, { label: string; color: string; bg: string; line: string; weight: number }> = {
  critical: { label: 'Critical', color: '#ff4a5e', bg: 'rgba(255,74,94,0.12)',   line: 'rgba(255,74,94,0.35)',   weight: 5 },
  high:     { label: 'High',     color: '#ff8847', bg: 'rgba(255,136,71,0.12)',  line: 'rgba(255,136,71,0.35)',  weight: 4 },
  medium:   { label: 'Medium',   color: '#ffc53d', bg: 'rgba(255,197,61,0.12)',  line: 'rgba(255,197,61,0.35)',  weight: 3 },
  low:      { label: 'Low',      color: '#4ea8ff', bg: 'rgba(78,168,255,0.12)',  line: 'rgba(78,168,255,0.35)',  weight: 2 },
  info:     { label: 'Info',     color: '#7a828f', bg: 'rgba(122,130,143,0.14)', line: 'rgba(122,130,143,0.35)', weight: 1 },
}

export const statusMeta: Record<string, { label: string; color: string }> = {
  open:            { label: 'Open',          color: '#ff8847' },
  triaged:         { label: 'Triaged',       color: '#4ea8ff' },
  'accepted-risk': { label: 'Accepted Risk', color: '#a8acb3' },
  resolved:        { label: 'Resolved',      color: '#34d399' },
  'false-positive':{ label: 'False Positive',color: '#7a828f' },
}

// ── Avatar ────────────────────────────────────────────────────────────
const avatarColors: Record<string, string> = {
  admin: '#ffaa00', operator: '#4ea8ff', viewer: '#34d399',
}
function colorForInitials(id: string) {
  const palette = ['#ffaa00','#4ea8ff','#34d399','#c084fc','#f472b6','#ff8847']
  let hash = 0
  for (let i = 0; i < id.length; i++) hash = id.charCodeAt(i) + ((hash << 5) - hash)
  return palette[Math.abs(hash) % palette.length]
}

export function Avatar({ id, size = 22 }: { id: string; size?: number }) {
  const initials = id.slice(0, 2).toUpperCase()
  const color = avatarColors[id] || colorForInitials(id)
  return (
    <div style={{
      width: size, height: size, borderRadius: 999,
      background: `linear-gradient(135deg, ${color}cc, ${color}66)`,
      display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
      fontSize: size * 0.42, fontWeight: 600, fontFamily: 'var(--mono)',
      color: '#0a0b0d', flexShrink: 0,
      boxShadow: 'inset 0 0 0 1px rgba(0,0,0,0.25)',
    }}>{initials}</div>
  )
}

export function AvatarStack({ ids, size = 22, max = 4 }: { ids: string[]; size?: number; max?: number }) {
  const shown = ids.slice(0, max)
  const extra = ids.length - shown.length
  return (
    <div style={{ display: 'inline-flex' }}>
      {shown.map((id, i) => (
        <div key={id} style={{ marginLeft: i ? -6 : 0, boxShadow: '0 0 0 2px var(--bg-1)', borderRadius: 999 }}>
          <Avatar id={id} size={size} />
        </div>
      ))}
      {extra > 0 && (
        <div style={{
          marginLeft: -6, width: size, height: size, borderRadius: 999,
          background: 'var(--bg-3)', color: 'var(--text-2)', fontSize: size * 0.4,
          display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
          boxShadow: '0 0 0 2px var(--bg-1)', fontFamily: 'var(--mono)',
        }}>+{extra}</div>
      )}
    </div>
  )
}

// ── SevPill ───────────────────────────────────────────────────────────
export function SevPill({ sev, compact, dot }: { sev: FindingSeverity; compact?: boolean; dot?: boolean }) {
  const m = sevMeta[sev]
  if (!m) return null
  if (dot) return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, color: 'var(--text-2)', fontSize: 12 }}>
      <span style={{ width: 7, height: 7, borderRadius: 2, background: m.color, boxShadow: `0 0 0 2px ${m.bg}` }} />
      {m.label}
    </span>
  )
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 6,
      padding: compact ? '1px 6px' : '2px 8px', borderRadius: 4,
      background: m.bg, color: m.color,
      fontFamily: 'var(--mono)', fontSize: 11, fontWeight: 600,
      letterSpacing: '0.03em', textTransform: 'uppercase',
      border: `1px solid ${m.line}`,
    }}>{m.label}</span>
  )
}

// ── StatusPill ────────────────────────────────────────────────────────
export function StatusPill({ status }: { status: FindingStatus | string }) {
  const m = statusMeta[status] || { label: status, color: '#7a828f' }
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 6,
      padding: '2px 7px', borderRadius: 4,
      background: 'var(--bg-3)', color: 'var(--text-2)',
      fontSize: 11.5, fontWeight: 500,
      border: '1px solid var(--line)',
    }}>
      <span style={{ width: 6, height: 6, borderRadius: 999, background: m.color }} />
      {m.label}
    </span>
  )
}

// ── Tag ───────────────────────────────────────────────────────────────
type TagTone = 'neutral' | 'accent' | 'ok' | 'warn'
const tagTones: Record<TagTone, { bg: string; color: string; border: string }> = {
  neutral: { bg: 'var(--bg-3)',      color: 'var(--text-2)', border: 'var(--line)'       },
  accent:  { bg: 'var(--accent-bg)', color: 'var(--accent)', border: 'var(--accent-line)' },
  ok:      { bg: 'rgba(52,211,153,0.10)', color: 'var(--ok)', border: 'rgba(52,211,153,0.30)' },
  warn:    { bg: 'rgba(255,136,71,0.10)', color: 'var(--high)', border: 'rgba(255,136,71,0.30)' },
}
export function Tag({ children, tone = 'neutral' }: { children: ReactNode; tone?: TagTone }) {
  const t = tagTones[tone]
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center',
      padding: '1px 7px', borderRadius: 4,
      background: t.bg, color: t.color, border: `1px solid ${t.border}`,
      fontFamily: 'var(--mono)', fontSize: 11,
    }}>{children}</span>
  )
}

// ── Button ────────────────────────────────────────────────────────────
type BtnVariant = 'primary' | 'secondary' | 'ghost' | 'outline' | 'danger'
type BtnSize = 'sm' | 'md' | 'lg'

const btnVariants: Record<BtnVariant, { bg: string; color: string; border: string; hover: string }> = {
  primary:   { bg: '#ffcc55',       color: '#1a1300', border: '1px solid rgba(0,0,0,0.2)', hover: '#ffd975' },
  secondary: { bg: 'var(--bg-3)',   color: 'var(--text)', border: '1px solid var(--line-2)', hover: '#23262d' },
  ghost:     { bg: 'transparent',   color: 'var(--text-2)', border: '1px solid transparent', hover: 'var(--bg-3)' },
  outline:   { bg: 'transparent',   color: 'var(--text)', border: '1px solid var(--line-2)', hover: 'var(--bg-3)' },
  danger:    { bg: 'rgba(255,74,94,0.12)', color: '#ff4a5e', border: '1px solid rgba(255,74,94,0.32)', hover: 'rgba(255,74,94,0.18)' },
}
const btnSizes: Record<BtnSize, { pad: string; fs: number; h: number; gap: number }> = {
  sm: { pad: '4px 8px',   fs: 12,   h: 26, gap: 5 },
  md: { pad: '6px 11px',  fs: 13,   h: 30, gap: 6 },
  lg: { pad: '8px 14px',  fs: 13.5, h: 34, gap: 7 },
}

interface ButtonProps {
  children?: ReactNode
  variant?: BtnVariant
  size?: BtnSize
  icon?: ReactNode
  iconRight?: ReactNode
  onClick?: () => void
  disabled?: boolean
  style?: CSSProperties
  title?: string
  active?: boolean
  type?: 'button' | 'submit' | 'reset'
}
export function Button({ children, variant = 'ghost', size = 'md', icon, iconRight, onClick, disabled, style, title, active, type = 'button' }: ButtonProps) {
  const v = btnVariants[variant]
  const s = btnSizes[size]
  const [hover, setHover] = useState(false)
  return (
    <button
      type={type}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      onClick={onClick}
      disabled={disabled}
      title={title}
      style={{
        display: 'inline-flex', alignItems: 'center', gap: s.gap,
        padding: s.pad, height: s.h,
        background: hover && !disabled ? v.hover : active ? v.hover : v.bg,
        color: v.color, border: v.border,
        borderRadius: 6, fontSize: s.fs, fontWeight: 500,
        letterSpacing: '-0.003em',
        transition: 'background 0.12s',
        opacity: disabled ? 0.5 : 1,
        cursor: disabled ? 'not-allowed' : 'pointer',
        ...style,
      }}
    >
      {icon}{children}{iconRight}
    </button>
  )
}

// ── IconButton ────────────────────────────────────────────────────────
export function IconButton({ icon, onClick, title, active, size = 28, style }: {
  icon: ReactNode; onClick?: () => void; title?: string; active?: boolean; size?: number; style?: CSSProperties
}) {
  const [hover, setHover] = useState(false)
  return (
    <button
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      onClick={onClick}
      title={title}
      style={{
        width: size, height: size, borderRadius: 6,
        background: active || hover ? 'var(--bg-3)' : 'transparent',
        color: active ? 'var(--text)' : 'var(--text-2)',
        display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
        border: '1px solid transparent',
        transition: 'background 0.12s',
        ...style,
      }}
    >{icon}</button>
  )
}

// ── Card ──────────────────────────────────────────────────────────────
export function Card({ children, style, padding = 16, hover, onClick }: {
  children: ReactNode; style?: CSSProperties; padding?: number; hover?: boolean; onClick?: () => void
}) {
  return (
    <div
      onClick={onClick}
      className={hover ? 'hover-card' : undefined}
      style={{ background: 'var(--bg-1)', border: '1px solid var(--line)', borderRadius: 'var(--radius-lg)', padding, ...style }}
    >{children}</div>
  )
}

// ── KPI ───────────────────────────────────────────────────────────────
export function KPI({ label, value, delta, deltaLabel, color, spark, icon }: {
  label: string; value: string | number; delta?: string; deltaLabel?: string; color?: string; spark?: ReactNode; icon?: ReactNode
}) {
  return (
    <Card padding={16} style={{ position: 'relative', overflow: 'hidden' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div style={{ color: 'var(--text-3)', fontSize: 12 }}>{label}</div>
        {icon && <div style={{ color: 'var(--text-3)' }}>{icon}</div>}
      </div>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, marginTop: 10 }}>
        <div style={{ fontSize: 28, fontWeight: 600, color: color || 'var(--text)', letterSpacing: '-0.02em', fontFamily: 'var(--mono)' }}>{value}</div>
        {delta && (
          <div style={{ fontSize: 11.5, color: delta.startsWith('-') ? 'var(--ok)' : 'var(--high)', fontFamily: 'var(--mono)' }}>{delta}</div>
        )}
      </div>
      {deltaLabel && <div style={{ color: 'var(--text-3)', fontSize: 11.5, marginTop: 4 }}>{deltaLabel}</div>}
      {spark && <div style={{ marginTop: 8 }}>{spark}</div>}
    </Card>
  )
}

// ── Sparkline ─────────────────────────────────────────────────────────
export function Sparkline({ data, color = 'var(--accent)', height = 24, width = 120, fill }: {
  data: number[]; color?: string; height?: number; width?: number; fill?: string
}) {
  if (data.length < 2) return null
  const max = Math.max(...data), min = Math.min(...data), range = max - min || 1
  const step = width / (data.length - 1)
  const points = data.map((v, i) => [i * step, height - ((v - min) / range) * height])
  const path = points.map((p, i) => (i === 0 ? 'M' : 'L') + p[0].toFixed(1) + ' ' + p[1].toFixed(1)).join(' ')
  const fillPath = path + ` L ${width} ${height} L 0 ${height} Z`
  return (
    <svg width={width} height={height} style={{ display: 'block' }}>
      {fill && <path d={fillPath} fill={fill} />}
      <path d={path} stroke={color} strokeWidth={1.5} fill="none" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

// ── Progress ──────────────────────────────────────────────────────────
export function Progress({ value, color = 'var(--accent)', height = 4, bg = 'var(--bg-3)' }: {
  value: number; color?: string; height?: number; bg?: string
}) {
  return (
    <div style={{ height, background: bg, borderRadius: 999, overflow: 'hidden' }}>
      <div style={{ width: `${Math.min(1, value) * 100}%`, height: '100%', background: color, borderRadius: 999 }} />
    </div>
  )
}

// ── SeverityBar ───────────────────────────────────────────────────────
export function SeverityBar({ counts, height = 6, width = 140 }: {
  counts: Partial<Record<string, number>>; height?: number; width?: number
}) {
  const order: FindingSeverity[] = ['critical', 'high', 'medium', 'low', 'info']
  const total = order.reduce((a, k) => a + (counts[k] || 0), 0)
  const segs = order.map(k => ({ key: k, val: counts[k] || 0 })).filter(s => s.val > 0)
  if (total === 0) return <div style={{ height, width, background: 'var(--bg-3)', borderRadius: 2 }} />
  return (
    <div style={{ display: 'flex', width, height, borderRadius: 2, overflow: 'hidden', background: 'var(--bg-3)' }}>
      {segs.map((s, i) => (
        <div key={s.key} style={{
          width: `${(s.val / total) * 100}%`,
          background: sevMeta[s.key as FindingSeverity]?.color || '#7a828f',
          borderRight: i < segs.length - 1 ? '1px solid var(--bg-1)' : 'none',
        }} />
      ))}
    </div>
  )
}

// ── Kbd ───────────────────────────────────────────────────────────────
export function Kbd({ children }: { children: ReactNode }) {
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
      minWidth: 18, height: 18, padding: '0 5px',
      background: 'var(--bg-3)', border: '1px solid var(--line)',
      borderRadius: 3, fontFamily: 'var(--mono)', fontSize: 10.5,
      color: 'var(--text-2)', boxShadow: '0 1px 0 rgba(0,0,0,0.4)',
    }}>{children}</span>
  )
}

// ── SectionHeader ─────────────────────────────────────────────────────
export function SectionHeader({ title, subtitle, right }: {
  title: string; subtitle?: string; right?: ReactNode
}) {
  return (
    <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', marginBottom: 14 }}>
      <div>
        <div style={{ fontSize: 14, fontWeight: 600, letterSpacing: '-0.01em' }}>{title}</div>
        {subtitle && <div style={{ color: 'var(--text-3)', fontSize: 12, marginTop: 2 }}>{subtitle}</div>}
      </div>
      {right}
    </div>
  )
}

// ── EmptyState ────────────────────────────────────────────────────────
export function EmptyState({ icon, title, body, action }: {
  icon?: string; title: string; body?: string; action?: ReactNode
}) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '48px 24px', gap: 12, textAlign: 'center' }}>
      {icon && <div style={{ color: 'var(--text-3)' }}><Ic name={icon} size={32} /></div>}
      <div style={{ fontSize: 15, fontWeight: 600 }}>{title}</div>
      {body && <div style={{ color: 'var(--text-3)', fontSize: 13, maxWidth: 320 }}>{body}</div>}
      {action}
    </div>
  )
}

// ── Spinner ───────────────────────────────────────────────────────────
export function Spinner({ size = 20 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" style={{ animation: 'spin 0.8s linear infinite' }}>
      <style>{`@keyframes spin { to { transform: rotate(360deg) } }`}</style>
      <circle cx="12" cy="12" r="10" stroke="var(--line-2)" strokeWidth="2.5" fill="none" />
      <path d="M12 2a10 10 0 0 1 10 10" stroke="var(--accent)" strokeWidth="2.5" fill="none" strokeLinecap="round" />
    </svg>
  )
}

// ── Modal ─────────────────────────────────────────────────────────────
export function Modal({ open, onClose, title, children, width = 480 }: {
  open: boolean; onClose: () => void; title: string; children: ReactNode; width?: number
}) {
  if (!open) return null
  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 200,
      background: 'rgba(0,0,0,0.7)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
    }} onClick={onClose}>
      <div style={{
        width, background: 'var(--bg-1)', border: '1px solid var(--line-2)',
        borderRadius: 10, boxShadow: 'var(--shadow-lg)', overflow: 'hidden',
      }} onClick={e => e.stopPropagation()}>
        <div style={{ padding: '14px 16px', borderBottom: '1px solid var(--line)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ fontSize: 14, fontWeight: 600 }}>{title}</div>
          <IconButton icon={<Ic name="close" size={14} />} onClick={onClose} size={24} />
        </div>
        {children}
      </div>
    </div>
  )
}

// ── Input ─────────────────────────────────────────────────────────────
export function Input({ value, onChange, placeholder, type = 'text', style, disabled, autoFocus, onKeyDown }: {
  value: string; onChange: (v: string) => void; placeholder?: string; type?: string;
  style?: CSSProperties; disabled?: boolean; autoFocus?: boolean; onKeyDown?: (e: React.KeyboardEvent) => void
}) {
  return (
    <input
      type={type}
      value={value}
      onChange={e => onChange(e.target.value)}
      placeholder={placeholder}
      disabled={disabled}
      autoFocus={autoFocus}
      onKeyDown={onKeyDown}
      style={{
        width: '100%', padding: '7px 10px', height: 32,
        background: 'var(--bg-2)', border: '1px solid var(--line-2)',
        borderRadius: 6, fontSize: 13, color: 'var(--text)',
        ...style,
      }}
    />
  )
}

export function Textarea({ value, onChange, placeholder, rows = 4 }: {
  value: string; onChange: (v: string) => void; placeholder?: string; rows?: number
}) {
  return (
    <textarea
      value={value}
      onChange={e => onChange(e.target.value)}
      placeholder={placeholder}
      rows={rows}
      style={{
        width: '100%', padding: '8px 10px',
        background: 'var(--bg-2)', border: '1px solid var(--line-2)',
        borderRadius: 6, fontSize: 13, color: 'var(--text)',
        resize: 'vertical', lineHeight: 1.5,
      }}
    />
  )
}

export function Select({ value, onChange, children, style }: {
  value: string; onChange: (v: string) => void; children: ReactNode; style?: CSSProperties
}) {
  return (
    <select
      value={value}
      onChange={e => onChange(e.target.value)}
      style={{
        padding: '6px 10px', height: 32,
        background: 'var(--bg-2)', border: '1px solid var(--line-2)',
        borderRadius: 6, fontSize: 13, color: 'var(--text)',
        cursor: 'pointer', ...style,
      }}
    >{children}</select>
  )
}

// ── FieldRow (label + control) ────────────────────────────────────────
export function FieldRow({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      <label style={{ fontSize: 12, color: 'var(--text-3)', fontWeight: 500 }}>{label}</label>
      {children}
    </div>
  )
}

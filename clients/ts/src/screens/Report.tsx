import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Ic } from '../components/Icon'
import { Button, Card, EmptyState, FieldRow, Input, Modal, SectionHeader, Select, SevPill, Spinner, Tag } from '../components/primitives'
import { getFindings } from '../api'
import type { Engagement, Finding } from '../types'

interface Props { engagement: Engagement | null }

type BlockType = 'heading' | 'text' | 'findings-table' | 'finding-detail' | 'scope-summary' | 'divider' | 'kpi-row'

interface Block {
  id: string
  type: BlockType
  content?: string
  findingIds?: string[]
  level?: 1 | 2 | 3
}

const BLOCK_TYPES: { type: BlockType; label: string; icon: string; desc: string }[] = [
  { type: 'heading', label: 'Heading', icon: 'type', desc: 'Section title H1–H3' },
  { type: 'text', label: 'Text block', icon: 'fileText', desc: 'Narrative paragraph' },
  { type: 'findings-table', label: 'Findings table', icon: 'bug', desc: 'Auto-populated findings list' },
  { type: 'finding-detail', label: 'Finding detail', icon: 'shield', desc: 'Expanded single finding' },
  { type: 'kpi-row', label: 'KPI row', icon: 'dashboard', desc: 'Severity counts at a glance' },
  { type: 'scope-summary', label: 'Scope summary', icon: 'target', desc: 'Engagement scope overview' },
  { type: 'divider', label: 'Divider', icon: 'minus', desc: 'Visual separator' },
]

function BlockPicker({ open, onClose, onAdd }: { open: boolean; onClose: () => void; onAdd: (t: BlockType) => void }) {
  return (
    <Modal open={open} onClose={onClose} title="Add block" width={480}>
      <div style={{ padding: 16, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
        {BLOCK_TYPES.map(b => (
          <button key={b.type} onClick={() => { onAdd(b.type); onClose() }} style={{
            display: 'flex', alignItems: 'flex-start', gap: 10, padding: '10px 12px', borderRadius: 8,
            border: '1px solid var(--line)', background: 'var(--bg-2)', textAlign: 'left',
            cursor: 'pointer', transition: 'border-color 0.15s',
          }}>
            <div style={{ width: 28, height: 28, borderRadius: 6, background: 'var(--bg-3)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
              <Ic name={b.icon} size={14} />
            </div>
            <div>
              <div style={{ fontSize: 12.5, fontWeight: 500 }}>{b.label}</div>
              <div style={{ fontSize: 11, color: 'var(--text-3)', marginTop: 2 }}>{b.desc}</div>
            </div>
          </button>
        ))}
      </div>
    </Modal>
  )
}

function HeadingBlock({ block, onChange }: { block: Block; onChange: (content: string, level: 1 | 2 | 3) => void }) {
  const sizes = { 1: 22, 2: 17, 3: 14 }
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
      <Select value={String(block.level || 1)} onChange={v => onChange(block.content || '', Number(v) as 1 | 2 | 3)} style={{ width: 56, fontSize: 11, flexShrink: 0 }}>
        <option value="1">H1</option>
        <option value="2">H2</option>
        <option value="3">H3</option>
      </Select>
      <input
        value={block.content || ''}
        onChange={e => onChange(e.target.value, block.level || 1)}
        placeholder="Section title…"
        style={{
          flex: 1, background: 'none', fontSize: sizes[block.level || 1],
          fontWeight: block.level === 1 ? 700 : block.level === 2 ? 600 : 500,
          color: 'var(--text)', letterSpacing: block.level === 1 ? '-0.03em' : '-0.01em',
        }}
      />
    </div>
  )
}

function TextBlock({ block, onChange }: { block: Block; onChange: (content: string) => void }) {
  return (
    <textarea
      value={block.content || ''}
      onChange={e => onChange(e.target.value)}
      placeholder="Write narrative text here…"
      rows={4}
      style={{
        width: '100%', background: 'none', fontSize: 13.5, color: 'var(--text-2)',
        lineHeight: 1.75, resize: 'vertical', fontFamily: 'inherit',
      }}
    />
  )
}

function FindingsTableBlock({ findings }: { findings: Finding[] }) {
  const sorted = [...findings].sort((a, b) => {
    const order = { critical: 0, high: 1, medium: 2, low: 3, info: 4 }
    return (order[a.severity] ?? 5) - (order[b.severity] ?? 5)
  })
  return (
    <div>
      <div style={{ display: 'grid', gridTemplateColumns: '80px 1fr 90px 90px', gap: 12, padding: '6px 12px', fontSize: 10.5, color: 'var(--text-3)', textTransform: 'uppercase', letterSpacing: '0.07em', borderBottom: '1px solid var(--line)' }}>
        <span>Severity</span><span>Title</span><span>Status</span><span>Target</span>
      </div>
      {sorted.map(f => (
        <div key={f.id} style={{ display: 'grid', gridTemplateColumns: '80px 1fr 90px 90px', gap: 12, alignItems: 'center', padding: '9px 12px', borderBottom: '1px solid var(--line)', fontSize: 12.5 }}>
          <SevPill sev={f.severity} />
          <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{f.title}</span>
          <Tag tone="neutral" style={{ fontSize: 10.5 }}>{f.status}</Tag>
          <span style={{ fontFamily: 'var(--mono)', fontSize: 11.5, color: 'var(--text-3)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{f.affected_target || '—'}</span>
        </div>
      ))}
      {sorted.length === 0 && (
        <div style={{ padding: '16px 12px', fontSize: 12, color: 'var(--text-3)', textAlign: 'center' }}>No findings in this engagement</div>
      )}
    </div>
  )
}

function KpiRowBlock({ findings }: { findings: Finding[] }) {
  const counts = { critical: 0, high: 0, medium: 0, low: 0, info: 0 }
  for (const f of findings) counts[f.severity] = (counts[f.severity] || 0) + 1
  const items = [
    { label: 'Critical', value: counts.critical, color: 'var(--crit)' },
    { label: 'High', value: counts.high, color: 'var(--high)' },
    { label: 'Medium', value: counts.medium, color: 'var(--med)' },
    { label: 'Low', value: counts.low, color: 'var(--low)' },
    { label: 'Info', value: counts.info, color: 'var(--text-3)' },
  ]
  return (
    <div style={{ display: 'flex', gap: 12 }}>
      {items.map(it => (
        <div key={it.label} style={{ flex: 1, padding: '14px 16px', background: 'var(--bg-2)', borderRadius: 8, border: '1px solid var(--line)' }}>
          <div style={{ fontSize: 24, fontWeight: 700, fontFamily: 'var(--mono)', color: it.value > 0 ? it.color : 'var(--text-4)' }}>{it.value}</div>
          <div style={{ fontSize: 11, color: 'var(--text-3)', marginTop: 4 }}>{it.label}</div>
        </div>
      ))}
    </div>
  )
}

function BlockRenderer({ block, findings, onChange, onDelete, onMoveUp, onMoveDown, canMoveUp, canMoveDown }:
  { block: Block; findings: Finding[]; onChange: (updates: Partial<Block>) => void; onDelete: () => void; onMoveUp: () => void; onMoveDown: () => void; canMoveUp: boolean; canMoveDown: boolean }) {
  const [hovered, setHovered] = useState(false)

  return (
    <div
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{ position: 'relative', borderRadius: 8, border: `1px solid ${hovered ? 'var(--line)' : 'transparent'}`, padding: '12px 14px', transition: 'border-color 0.15s' }}
    >
      {hovered && (
        <div style={{ position: 'absolute', right: 10, top: 10, display: 'flex', gap: 3, background: 'var(--bg-1)', border: '1px solid var(--line)', borderRadius: 6, padding: '2px 4px' }}>
          <button disabled={!canMoveUp} onClick={onMoveUp} style={{ color: canMoveUp ? 'var(--text-2)' : 'var(--text-4)', padding: '2px 5px', borderRadius: 4, fontSize: 11 }}>↑</button>
          <button disabled={!canMoveDown} onClick={onMoveDown} style={{ color: canMoveDown ? 'var(--text-2)' : 'var(--text-4)', padding: '2px 5px', borderRadius: 4, fontSize: 11 }}>↓</button>
          <button onClick={onDelete} style={{ color: 'var(--crit)', padding: '2px 5px', borderRadius: 4, fontSize: 11 }}>✕</button>
        </div>
      )}

      {block.type === 'heading' && (
        <HeadingBlock block={block} onChange={(content, level) => onChange({ content, level })} />
      )}
      {block.type === 'text' && (
        <TextBlock block={block} onChange={content => onChange({ content })} />
      )}
      {block.type === 'findings-table' && (
        <div>
          <div style={{ fontSize: 10.5, color: 'var(--text-3)', textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 8 }}>Findings</div>
          <FindingsTableBlock findings={findings} />
        </div>
      )}
      {block.type === 'kpi-row' && (
        <div>
          <div style={{ fontSize: 10.5, color: 'var(--text-3)', textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 8 }}>Summary</div>
          <KpiRowBlock findings={findings} />
        </div>
      )}
      {block.type === 'scope-summary' && (
        <div style={{ padding: '10px 14px', background: 'var(--bg-2)', borderRadius: 6 }}>
          <div style={{ fontSize: 12, color: 'var(--text-3)', marginBottom: 6 }}>Scope block — renders engagement scope at export time</div>
          <div style={{ display: 'flex', gap: 6 }}>
            {['host', 'ip', 'cidr', 'url', 'wildcard'].map(t => (
              <span key={t} style={{ padding: '2px 8px', background: 'var(--bg-3)', borderRadius: 4, fontSize: 11, color: 'var(--text-2)', fontFamily: 'var(--mono)' }}>{t}</span>
            ))}
          </div>
        </div>
      )}
      {block.type === 'divider' && (
        <div style={{ borderTop: '1px solid var(--line)', margin: '6px 0' }} />
      )}
    </div>
  )
}

const DEFAULT_BLOCKS: Block[] = [
  { id: '1', type: 'heading', level: 1, content: 'Penetration Test Report' },
  { id: '2', type: 'text', content: 'This report summarises the findings identified during the authorised penetration test. All testing was conducted within the agreed scope and rules of engagement.' },
  { id: '3', type: 'kpi-row' },
  { id: '4', type: 'heading', level: 2, content: 'Scope' },
  { id: '5', type: 'scope-summary' },
  { id: '6', type: 'heading', level: 2, content: 'Findings' },
  { id: '7', type: 'findings-table' },
]

export default function Report({ engagement }: Props) {
  const [blocks, setBlocks] = useState<Block[]>(DEFAULT_BLOCKS)
  const [pickerOpen, setPickerOpen] = useState(false)
  const [exportFormat, setExportFormat] = useState<'pdf' | 'md' | 'json'>('pdf')
  const [exportOpen, setExportOpen] = useState(false)

  const { data: findings = [], isLoading } = useQuery({
    queryKey: ['findings', engagement?.id],
    queryFn: () => getFindings(engagement!.id),
    enabled: !!engagement?.id,
  })

  const addBlock = (type: BlockType) => {
    const id = String(Date.now())
    const defaults: Partial<Block> = type === 'heading' ? { level: 2, content: '' } : { content: '' }
    setBlocks(prev => [...prev, { id, type, ...defaults }])
  }

  const updateBlock = (id: string, updates: Partial<Block>) => {
    setBlocks(prev => prev.map(b => b.id === id ? { ...b, ...updates } : b))
  }

  const deleteBlock = (id: string) => {
    setBlocks(prev => prev.filter(b => b.id !== id))
  }

  const moveBlock = (id: string, dir: -1 | 1) => {
    setBlocks(prev => {
      const idx = prev.findIndex(b => b.id === id)
      if (idx + dir < 0 || idx + dir >= prev.length) return prev
      const next = [...prev]
      ;[next[idx], next[idx + dir]] = [next[idx + dir], next[idx]]
      return next
    })
  }

  if (!engagement) return <EmptyState icon="fileText" title="No engagement selected" />

  return (
    <div style={{ display: 'flex', height: 'calc(100vh - 46px)' }}>
      {/* Canvas */}
      <div style={{ flex: 1, overflow: 'auto', background: 'var(--bg-1)', padding: '32px 0' }}>
        <div style={{ maxWidth: 760, margin: '0 auto', background: 'var(--bg)', borderRadius: 12, border: '1px solid var(--line)', minHeight: 600 }}>
          {/* Doc header */}
          <div style={{ padding: '20px 24px', borderBottom: '1px solid var(--line)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div>
              <div style={{ fontSize: 13, fontWeight: 600 }}>{engagement.name}</div>
              <div style={{ fontSize: 11, color: 'var(--text-3)', marginTop: 2, fontFamily: 'var(--mono)' }}>
                Draft · {new Date().toLocaleDateString()}
              </div>
            </div>
            <div style={{ display: 'flex', gap: 6 }}>
              <Tag tone="neutral">Draft</Tag>
              <Button variant="secondary" size="sm" icon={<Ic name="download" size={13} />} onClick={() => setExportOpen(true)}>
                Export
              </Button>
            </div>
          </div>

          {/* Blocks */}
          <div style={{ padding: '16px 24px' }}>
            {isLoading ? (
              <div style={{ display: 'flex', justifyContent: 'center', padding: 48 }}><Spinner /></div>
            ) : (
              blocks.map((block, idx) => (
                <BlockRenderer
                  key={block.id}
                  block={block}
                  findings={findings}
                  onChange={updates => updateBlock(block.id, updates)}
                  onDelete={() => deleteBlock(block.id)}
                  onMoveUp={() => moveBlock(block.id, -1)}
                  onMoveDown={() => moveBlock(block.id, 1)}
                  canMoveUp={idx > 0}
                  canMoveDown={idx < blocks.length - 1}
                />
              ))
            )}

            {/* Add block button */}
            <button onClick={() => setPickerOpen(true)} style={{
              display: 'flex', alignItems: 'center', gap: 7, marginTop: 8,
              padding: '8px 12px', borderRadius: 7, fontSize: 12.5, color: 'var(--text-3)',
              border: '1px dashed var(--line)', width: '100%', cursor: 'pointer',
              transition: 'color 0.15s, border-color 0.15s',
            }}>
              <Ic name="plus" size={13} /> Add block
            </button>
          </div>
        </div>
      </div>

      {/* Sidebar */}
      <div style={{ width: 240, flexShrink: 0, borderLeft: '1px solid var(--line)', background: 'var(--bg-1)', padding: '16px 14px', display: 'flex', flexDirection: 'column', gap: 16, overflow: 'auto' }}>
        <SectionHeader title="Document" subtitle={`${blocks.length} blocks`} />

        <div>
          <div style={{ fontSize: 11, color: 'var(--text-3)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 8 }}>Blocks</div>
          {blocks.map((b, idx) => (
            <div key={b.id} style={{ display: 'flex', alignItems: 'center', gap: 7, padding: '5px 7px', borderRadius: 5, fontSize: 11.5, color: 'var(--text-2)', marginBottom: 1 }}>
              <Ic name={BLOCK_TYPES.find(t => t.type === b.type)?.icon || 'file'} size={11} style={{ color: 'var(--text-3)', flexShrink: 0 }} />
              <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1 }}>
                {b.type === 'heading' ? (b.content || 'Heading') : b.type.replace(/-/g, ' ')}
              </span>
            </div>
          ))}
        </div>

        <div>
          <div style={{ fontSize: 11, color: 'var(--text-3)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 8 }}>Stats</div>
          {[
            { label: 'Total findings', value: findings.length },
            { label: 'Critical', value: findings.filter(f => f.severity === 'critical').length },
            { label: 'High', value: findings.filter(f => f.severity === 'high').length },
            { label: 'Open', value: findings.filter(f => f.status === 'open').length },
          ].map(s => (
            <div key={s.label} style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0', fontSize: 12, borderBottom: '1px solid var(--line)' }}>
              <span style={{ color: 'var(--text-3)' }}>{s.label}</span>
              <span style={{ fontFamily: 'var(--mono)', fontWeight: 600 }}>{s.value}</span>
            </div>
          ))}
        </div>

        <Button variant="primary" icon={<Ic name="download" size={13} />} onClick={() => setExportOpen(true)}>Export report</Button>
      </div>

      <BlockPicker open={pickerOpen} onClose={() => setPickerOpen(false)} onAdd={addBlock} />

      <Modal open={exportOpen} onClose={() => setExportOpen(false)} title="Export report" width={400}>
        <div style={{ padding: 20, display: 'flex', flexDirection: 'column', gap: 14 }}>
          <FieldRow label="Format">
            <Select value={exportFormat} onChange={v => setExportFormat(v as 'pdf' | 'md' | 'json')}>
              <option value="pdf">PDF</option>
              <option value="md">Markdown</option>
              <option value="json">JSON (machine-readable)</option>
            </Select>
          </FieldRow>
          <div style={{ padding: '10px 12px', background: 'var(--bg-2)', borderRadius: 6, fontSize: 12, color: 'var(--text-3)' }}>
            Exports are generated server-side and include all finding details, scope, and metadata.
          </div>
          <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
            <Button variant="ghost" onClick={() => setExportOpen(false)}>Cancel</Button>
            <Button variant="primary" icon={<Ic name="download" size={13} />}
              onClick={() => { window.open(`/api/engagements/${engagement?.id}/report?format=${exportFormat}`, '_blank'); setExportOpen(false) }}>
              Download
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  )
}

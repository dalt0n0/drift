import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Button, FieldRow, Input, Modal, Textarea } from './primitives'
import { createEngagement } from '../api'
import type { Engagement } from '../types'

interface Props {
  open: boolean
  onClose: () => void
  onCreated?: (e: Engagement) => void
}

export default function NewEngagementModal({ open, onClose, onCreated }: Props) {
  const qc = useQueryClient()
  const [title, setTitle] = useState('')
  const [clientName, setClientName] = useState('')
  const [description, setDescription] = useState('')
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')
  const [error, setError] = useState<string | null>(null)

  const reset = () => {
    setTitle(''); setClientName(''); setDescription('')
    setStartDate(''); setEndDate(''); setError(null)
  }

  const mutation = useMutation({
    mutationFn: () => createEngagement({
      title: title.trim(),
      client_name: clientName.trim(),
      description: description.trim() || undefined,
      start_date: startDate ? new Date(startDate).toISOString() : undefined,
      end_date: endDate ? new Date(endDate).toISOString() : undefined,
    } as Partial<Engagement>),
    onSuccess: (eng) => {
      qc.invalidateQueries({ queryKey: ['engagements'] })
      reset()
      onCreated?.(eng)
      onClose()
    },
    onError: (err: any) => {
      const detail = err?.response?.data?.detail
      setError(typeof detail === 'string' ? detail : detail?.detail || 'Failed to create engagement')
    },
  })

  const submit = () => {
    setError(null)
    if (!title.trim()) { setError('Title is required'); return }
    if (!clientName.trim()) { setError('Client name is required'); return }
    mutation.mutate()
  }

  return (
    <Modal open={open} onClose={() => { reset(); onClose() }} title="New engagement" width={520}>
      <div style={{ padding: 18, display: 'flex', flexDirection: 'column', gap: 14 }}>
        <FieldRow label="Title">
          <Input value={title} onChange={setTitle} placeholder="e.g. Q2 External Pentest" autoFocus />
        </FieldRow>
        <FieldRow label="Client name">
          <Input value={clientName} onChange={setClientName} placeholder="e.g. Acme Corp" />
        </FieldRow>
        <FieldRow label="Description">
          <Textarea value={description} onChange={setDescription} placeholder="Optional notes about scope, goals, or context…" rows={3} />
        </FieldRow>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
          <FieldRow label="Start date">
            <Input value={startDate} onChange={setStartDate} type="date" />
          </FieldRow>
          <FieldRow label="End date">
            <Input value={endDate} onChange={setEndDate} type="date" />
          </FieldRow>
        </div>
        {error && (
          <div style={{ padding: '8px 10px', background: 'rgba(255,74,94,0.08)', border: '1px solid rgba(255,74,94,0.3)', borderRadius: 6, color: '#ff8a99', fontSize: 12 }}>
            {error}
          </div>
        )}
        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 4 }}>
          <Button variant="ghost" onClick={() => { reset(); onClose() }} disabled={mutation.isPending}>Cancel</Button>
          <Button variant="primary" onClick={submit} disabled={mutation.isPending}>
            {mutation.isPending ? 'Creating…' : 'Create engagement'}
          </Button>
        </div>
      </div>
    </Modal>
  )
}

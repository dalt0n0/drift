import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Button, FieldRow, Input, Modal, Select, Textarea } from './primitives'
import { createEngagement, getOrganizations, createOrganization } from '../api'
import type { Engagement, Organization } from '../types'

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
  const [organizationId, setOrganizationId] = useState('')
  const [newOrgName, setNewOrgName] = useState('')
  const [creatingOrg, setCreatingOrg] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const { data: organizations = [] as Organization[] } = useQuery({
    queryKey: ['organizations'],
    queryFn: getOrganizations,
    enabled: open,
  })

  const createOrgMutation = useMutation({
    mutationFn: () => createOrganization({ name: newOrgName.trim() }),
    onSuccess: (org) => {
      qc.invalidateQueries({ queryKey: ['organizations'] })
      setOrganizationId(org.id)
      setNewOrgName('')
      setCreatingOrg(false)
    },
    onError: (err: any) => {
      const detail = err?.response?.data?.detail
      setError(typeof detail === 'string' ? detail : 'Failed to create organization')
    },
  })

  const reset = () => {
    setTitle(''); setClientName(''); setDescription('')
    setStartDate(''); setEndDate(''); setOrganizationId('')
    setNewOrgName(''); setCreatingOrg(false); setError(null)
  }

  const mutation = useMutation({
    mutationFn: () => createEngagement({
      title: title.trim(),
      client_name: clientName.trim(),
      description: description.trim() || undefined,
      start_date: startDate ? new Date(startDate).toISOString() : undefined,
      end_date: endDate ? new Date(endDate).toISOString() : undefined,
      organization_id: organizationId || undefined,
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
        <FieldRow label="Organization">
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            <Select value={organizationId} onChange={setOrganizationId}>
              <option value="">— None —</option>
              {organizations.map(o => (
                <option key={o.id} value={o.id}>{o.name}</option>
              ))}
            </Select>
            {creatingOrg ? (
              <div style={{ display: 'flex', gap: 8 }}>
                <Input value={newOrgName} onChange={setNewOrgName} placeholder="New organization name" autoFocus />
                <button
                  onClick={() => { if (newOrgName.trim()) createOrgMutation.mutate() }}
                  disabled={!newOrgName.trim() || createOrgMutation.isPending}
                  style={{
                    padding: '0 12px', height: 32, borderRadius: 6, fontSize: 12,
                    background: 'var(--accent)', color: '#1a1300', fontWeight: 600,
                    cursor: 'pointer', flexShrink: 0,
                    opacity: !newOrgName.trim() || createOrgMutation.isPending ? 0.5 : 1,
                  }}
                >
                  {createOrgMutation.isPending ? '…' : 'Create'}
                </button>
                <button
                  onClick={() => { setCreatingOrg(false); setNewOrgName('') }}
                  style={{ padding: '0 10px', height: 32, borderRadius: 6, fontSize: 12, background: 'var(--bg-3)', color: 'var(--text-2)', cursor: 'pointer' }}
                >
                  Cancel
                </button>
              </div>
            ) : (
              <button
                onClick={() => setCreatingOrg(true)}
                style={{ alignSelf: 'flex-start', fontSize: 12, color: 'var(--accent)', background: 'none', padding: 0, cursor: 'pointer' }}
              >
                + Create new organization
              </button>
            )}
          </div>
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

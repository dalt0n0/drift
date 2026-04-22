import { api } from './client'
import type {
  LoginResponse, User, Engagement, ScopeItem,
  Finding, EngagementRun, AuditEntry, Organization,
} from '../types'

// ── Auth ──────────────────────────────────────────────────────────────
export const login = (username: string, password: string) =>
  api.post<LoginResponse>('/auth/login', { username, password }).then(r => r.data)

export const getMe = () =>
  api.get<User>('/users/me').then(r => r.data)

export const logout = () =>
  api.post('/auth/logout').catch(() => {})

// ── Engagements ───────────────────────────────────────────────────────
export const getEngagements = () =>
  api.get<{ items: Engagement[] }>('/engagements').then(r => r.data.items)

export const getEngagement = (id: string) =>
  api.get<Engagement>(`/engagements/${id}`).then(r => r.data)

export const createEngagement = (data: Partial<Engagement>) =>
  api.post<Engagement>('/engagements', data).then(r => r.data)

export const updateEngagement = (id: string, data: Partial<Engagement>) =>
  api.patch<Engagement>(`/engagements/${id}`, data).then(r => r.data)

export const updateEngagementStatus = (engagementId: string, status: string) =>
  api.patch<Engagement>(`/engagements/${engagementId}`, { status }).then(r => r.data)

export const deleteEngagement = (engagementId: string) =>
  api.delete(`/engagements/${engagementId}`)

// ── Scope ─────────────────────────────────────────────────────────────
export const getScope = (engagementId: string) =>
  api.get<ScopeItem[]>(`/engagements/${engagementId}/scope`).then(r => r.data)

export const addScopeItem = (engagementId: string, data: Partial<ScopeItem>) =>
  api.post<ScopeItem>(`/engagements/${engagementId}/scope`, data).then(r => r.data)

export const deleteScopeItem = (engagementId: string, itemId: string) =>
  api.delete(`/engagements/${engagementId}/scope/${itemId}`)

// ── Findings ──────────────────────────────────────────────────────────
export const getFindings = (engagementId: string) =>
  api.get<{ findings: Finding[] }>(`/engagements/${engagementId}/findings`).then(r => r.data.findings)

export const getFinding = (engagementId: string, id: string) =>
  api.get<Finding>(`/engagements/${engagementId}/findings/${id}`).then(r => r.data)

export const createFinding = (engagementId: string, data: Partial<Finding>) =>
  api.post<Finding>(`/engagements/${engagementId}/findings`, data).then(r => r.data)

export const updateFinding = (engagementId: string, id: string, data: Partial<Finding>) =>
  api.patch<Finding>(`/engagements/${engagementId}/findings/${id}`, data).then(r => r.data)

export const deleteFinding = (engagementId: string, id: string) =>
  api.delete(`/engagements/${engagementId}/findings/${id}`)

export const acceptFinding = (findingId: string, engagementId: string) =>
  api.patch<Finding>(`/engagements/${engagementId}/findings/${findingId}`, { status: 'open' }).then(r => r.data)

export const rejectFinding = (findingId: string, engagementId: string) =>
  api.patch<Finding>(`/engagements/${engagementId}/findings/${findingId}`, { status: 'false_positive' }).then(r => r.data)

// ── Runs ──────────────────────────────────────────────────────────────
export const getRuns = (engagementId: string) =>
  api.get<{ items: EngagementRun[] }>(`/engagements/${engagementId}/runs`).then(r => r.data.items)

export const getRun = (engagementId: string, runId: string) =>
  api.get<EngagementRun>(`/engagements/${engagementId}/runs/${runId}`).then(r => r.data)

export const createRun = (engagementId: string, plugin: string, params: Record<string, unknown>) =>
  api.post<EngagementRun>(`/engagements/${engagementId}/runs`, {
    plugin_names: [plugin],
    safe_mode: false,
    params,
  }).then(r => r.data)

export const confirmAuthorization = (engagementId: string) =>
  api.post<Engagement>(`/engagements/${engagementId}/authorization/confirm`).then(r => r.data)

export const cancelRun = (runId: string) =>
  api.post<EngagementRun>(`/runs/${runId}/cancel`).then(r => r.data)

export const deleteRun = (runId: string) =>
  api.delete(`/runs/${runId}`)

// ── Reports ───────────────────────────────────────────────────────────
export const downloadReport = async (
  engagementId: string,
  reportType: 'executive' | 'technical' | 'client',
  format: 'pdf' | 'html' | 'json' | 'csv' | 'sarif',
  token: string,
): Promise<void> => {
  const res = await fetch(`/api/reports/engagements/${engagementId}/reports`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
    body: JSON.stringify({ report_type: reportType, format }),
  })
  if (!res.ok) throw new Error(`Report generation failed: ${res.status}`)
  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `drift_${reportType}_${engagementId}.${format}`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

export const changePassword = (current_password: string, new_password: string) =>
  api.post('/auth/change-password', { current_password, new_password })

// ── Audit ─────────────────────────────────────────────────────────────
export const getAudit = (limit = 50) =>
  api.get<{ items: AuditEntry[] }>(`/audit?limit=${limit}`).then(r => r.data.items)

// ── SBOM ──────────────────────────────────────────────────────────────
export const getSbomSummary = () =>
  api.get('/sbom').then(r => r.data)

// ── Users ─────────────────────────────────────────────────────────────
export const getUsers = () =>
  api.get<User[]>('/users').then(r => r.data)

export const createUser = (body: {
  username: string
  email: string
  password: string
  full_name?: string
  role?: string
  must_change_password?: boolean
}) => api.post<User>('/users/', body).then(r => r.data)

// ── Organizations ─────────────────────────────────────────────────────
export const getOrganizations = (): Promise<Organization[]> =>
  api.get<{ items: Organization[] }>('/organizations?page_size=200').then(r =>
    r.data.items ?? (r.data as unknown as Organization[])
  )

export const createOrganization = (body: { name: string; description?: string; website?: string }) =>
  api.post<Organization>('/organizations', body).then(r => r.data)

export const deleteOrganization = (id: string) =>
  api.delete(`/organizations/${id}`)

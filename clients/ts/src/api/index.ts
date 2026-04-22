import { api } from './client'
import type {
  LoginResponse, User, Engagement, ScopeItem,
  Finding, EngagementRun, AuditEntry,
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

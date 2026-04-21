export type Role = 'admin' | 'operator' | 'viewer'
export type EngagementStatus = 'draft' | 'active' | 'completed' | 'archived' | 'paused'
export type FindingSeverity = 'critical' | 'high' | 'medium' | 'low' | 'info'
export type FindingStatus = 'open' | 'triaged' | 'accepted-risk' | 'resolved' | 'false-positive'
export type RunStatus = 'pending' | 'running' | 'completed' | 'failed' | 'error'
export type ScopeType = 'host' | 'ip' | 'cidr' | 'url' | 'wildcard'

export interface User {
  id: string
  username: string
  email: string
  full_name: string
  role: Role
  is_active: boolean
  created_at: string
}

export interface Engagement {
  id: string
  name: string
  description: string
  status: EngagementStatus
  start_date?: string
  end_date?: string
  client_name?: string
  engagement_type?: string
  created_by: string
  created_at: string
  updated_at: string
}

export interface ScopeItem {
  id: string
  engagement_id: string
  type: ScopeType
  value: string
  notes?: string
  created_at: string
}

export interface Finding {
  id: string
  engagement_id: string
  title: string
  description?: string
  severity: FindingSeverity
  status: FindingStatus
  cvss_score?: number
  cve_ids?: string[]
  target?: string
  category?: string
  cwe?: string
  tags?: string[]
  assignee_id?: string
  reporter_id?: string
  remediation?: string
  created_at: string
  updated_at: string
}

export interface EngagementRun {
  id: string
  engagement_id: string
  plugin: string
  params: Record<string, unknown>
  status: RunStatus
  stdout?: string
  stderr?: string
  artifact_path?: string
  error?: string
  started_at?: string
  finished_at?: string
  created_at: string
}

export interface AuditEntry {
  id: string
  action: string
  actor_id?: string
  resource_type?: string
  resource_id?: string
  detail?: Record<string, unknown>
  timestamp: string
}

export interface LoginResponse {
  access_token: string
  token_type: string
  refresh_token: string
}

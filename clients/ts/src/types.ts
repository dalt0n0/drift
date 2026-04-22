export type Role = 'admin' | 'operator' | 'lead' | 'tester' | 'viewer'
export type EngagementStatus = 'draft' | 'active' | 'completed' | 'archived' | 'paused'
export type FindingSeverity = 'critical' | 'high' | 'medium' | 'low' | 'info'
export type FindingStatus = 'suggested' | 'open' | 'confirmed' | 'false_positive' | 'remediated' | 'accepted_risk'
export type RunStatus = 'pending' | 'running' | 'completed' | 'failed' | 'error' | 'cancelled'
export type ScopeType = 'domain' | 'ip' | 'cidr' | 'url' | 'wildcard'

export interface User {
  id: string
  username: string
  email: string
  full_name: string
  role: Role
  is_active: boolean
  created_at: string
  must_change_password: boolean
}

export interface Engagement {
  id: string
  title: string
  client_name: string
  description?: string
  status: EngagementStatus
  start_date?: string
  end_date?: string
  owner_id: string
  organization_id?: string
  authorization_letter_path?: string
  authorization_hash?: string
  authorization_confirmed?: boolean
  created_at: string
  updated_at: string
}

export interface Organization {
  id: string
  name: string
  description: string | null
  website: string | null
  created_by: string | null
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
  affected_target?: string
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
  status: RunStatus
  pipeline_config: {
    plugins: string[]
    safe_mode: boolean
    params: Record<string, unknown>
  } | null
  checkpoint: {
    completed_plugins: string[]
    current_plugin: string | null
    logs?: string[]
    results?: Record<string, { status: string; error?: string; exit_code?: number; duration_seconds?: number }>
  } | null
  triggered_by: string | null
  started_at: string | null
  completed_at: string | null
  created_at: string
  updated_at: string
  error_message: string | null
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
  expires_in: number
  must_change_password: boolean
}

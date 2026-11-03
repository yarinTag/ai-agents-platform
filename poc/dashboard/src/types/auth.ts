export interface AuthUser {
  id: string;
  organization_id: string;
  email: string;
  full_name: string;
  role: 'ORG_ADMIN' | 'MANAGER' | 'OPERATOR' | 'MEMBER' | string;
  status: string;
  created_at?: string;
  last_login_at?: string;
}

export interface Organization {
  id: string;
  name: string;
  slug: string;
  domain?: string | null;
  settings_json?: string;
  created_at?: string;
  updated_at?: string;
}

export interface Department {
  id: string;
  department_id?: string;
  name: string;
  description?: string | null;
  monthly_budget_usd: number;
  current_spend_usd: number;
  budget_action: 'HARD_STOP' | 'ALERT_ONLY' | 'NOTIFY_ADMIN' | string;
  alert_threshold_pct: number;
  organization_id?: string | null;
  created_at?: string;
  updated_at?: string;
  department_role?: string;
}

export interface DepartmentMember {
  id: string;
  department_id: string;
  user_id: string;
  email: string;
  full_name: string;
  role: string;
  joined_at?: string;
  status?: string;
}

export interface OrganizationUser {
  id: string;
  organization_id: string;
  email: string;
  full_name: string;
  role: string;
  status: string;
  created_at?: string;
  last_login_at?: string;
}

export interface InvitationRecord {
  id: string;
  token: string;
  email: string;
  role: string;
  status: string;
  expires_at?: string;
  created_at?: string;
  department_id?: string;
  organization_id?: string;
}

export interface BulkInviteResponse {
  department_id: string;
  invited_count: number;
  invitations: InvitationRecord[];
}

export interface AuthResponse {
  token: string;
  user: AuthUser;
  organization: Organization;
  departments: Department[];
}

export interface CurrentUserProfileResponse {
  user: AuthUser;
  organization: Organization | null;
  departments: Department[];
}

export interface LoginDto {
  email: string;
  password: string;
}

export interface RegisterOrgDto {
  name: string;
  slug: string;
  domain?: string;
  admin_email: string;
  admin_name: string;
  admin_password: string;
}

export interface AcceptInviteDto {
  invite_token: string;
  full_name: string;
  password: string;
}

export interface CreateDepartmentDto {
  name: string;
  description?: string;
  monthly_budget_usd?: number;
  budget_action?: string;
  alert_threshold_pct?: number;
  organization_id?: string;
}

export interface BulkInviteDto {
  emails: string[];
  role: string;
  expires_in_days?: number;
}

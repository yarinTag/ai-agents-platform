import { api } from './httpClient';
import type {
  AuthResponse, CurrentUserProfileResponse, Department, DepartmentMember,
  BulkInviteResponse, OrganizationUser, LoginDto, RegisterOrgDto,
  AcceptInviteDto, CreateDepartmentDto, BulkInviteDto,
} from '../types/auth';

// Enterprise Organization & Authentication
export const loginOrganizationUser = (data: LoginDto) =>
  api.post<AuthResponse>('/api/v1/auth/login', data);

export const registerOrganization = (data: RegisterOrgDto) =>
  api.post<AuthResponse>('/api/v1/auth/org-register', data);

export const acceptOrgInvitation = (data: AcceptInviteDto) =>
  api.post<AuthResponse>('/api/v1/invitations/accept', data);

export const getCurrentUserProfile = () =>
  api.get<CurrentUserProfileResponse>('/api/v1/auth/me');

export const getDepartments = (organization_id?: string) =>
  api.get<Department[]>('/api/v1/departments', {
    params: organization_id ? { organization_id } : {},
    // Directory reads list every authorized department, independent of header selection.
    headers: { 'X-Department-ID': false },
  });

export const createDepartment = (data: CreateDepartmentDto) =>
  api.post<Department>('/api/v1/departments', data);

export const getDepartmentMembers = (deptId: string) =>
  api.get<DepartmentMember[]>(`/api/v1/departments/${encodeURIComponent(deptId)}/members`, {
    headers: { 'X-Department-ID': deptId },
  });

export const bulkInviteDepartmentMembers = (deptId: string, data: BulkInviteDto) =>
  api.post<BulkInviteResponse>(`/api/v1/departments/${encodeURIComponent(deptId)}/members/bulk-invite`, data, {
    headers: { 'X-Department-ID': deptId },
  });

export const removeDepartmentMember = (deptId: string, userId: string) =>
  api.delete<{ status: string; message: string }>(`/api/v1/departments/${encodeURIComponent(deptId)}/members/${encodeURIComponent(userId)}`, {
    headers: { 'X-Department-ID': deptId },
  });

export const getOrganizationUsers = (orgId: string) =>
  api.get<OrganizationUser[]>(`/api/v1/organizations/${orgId}/users`);

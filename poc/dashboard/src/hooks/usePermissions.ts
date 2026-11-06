import { useAuth } from '../context/AuthContext';

import { effectivePermissions } from '../services/accessPermissions';
export function usePermissions() {
  const { user, departments, activeDepartmentId } = useAuth();
  const membership = departments.find((department) => (department.id || department.department_id) === activeDepartmentId);
  return effectivePermissions(user?.role, membership?.department_role);
}

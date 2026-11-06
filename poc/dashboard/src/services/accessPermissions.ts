const ranks: Record<string, number> = { MEMBER: 1, OPERATOR: 2, MANAGER: 3, ORG_ADMIN: 4 };

export function effectivePermissions(role?: string, departmentRole?: string) {
  const isAdmin = role === 'ORG_ADMIN';
  const rank = isAdmin ? 4 : Math.min(ranks[role || ''] || 0, ranks[departmentRole || ''] || 0);
  return { isAdmin, canRead: rank >= 1, canOperate: rank >= 2, canManage: rank >= 3, rank };
}

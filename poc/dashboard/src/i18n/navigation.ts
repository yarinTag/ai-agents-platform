import { useTranslation } from './I18nContext';
const en = {
  operations: 'OPERATIONS', workflows: 'Workflows', flow: 'Live Flow', agents: 'Agents Roster',
  tools: 'TOOLS & PLUGINS', plugins: 'Plugins Hub', mcp: 'MCP Hub', tasks: 'Tasks Queue',
  workspace: 'WORKSPACE & DATA', projects: 'Projects', calendar: 'Schedule & Calendar', metrics: 'System Metrics',
  governance: 'ORGANIZATION & GOVERNANCE', organization: 'Org & Teams', expand: 'Expand Menu', collapse: 'Collapse Menu',
  expandSidebar: 'Expand Sidebar', collapseSidebar: 'Collapse Sidebar', active: 'Active platform',
  allDepartments: 'All Departments', department: 'Department', logout: 'Log out', logoutPrompt: 'Are you sure you want to log out?', cancel: 'Cancel',
};
const he: typeof en = {
  operations: 'תפעול', workflows: 'תהליכי עבודה', flow: 'זרימה חיה', agents: 'רשימת סוכנים',
  tools: 'כלים ותוספים', plugins: 'מרכז התוספים', mcp: 'מרכז MCP', tasks: 'תור משימות',
  workspace: 'סביבת עבודה ונתונים', projects: 'פרויקטים', calendar: 'תזמון ולוח שנה', metrics: 'מדדי מערכת',
  governance: 'ארגון וממשל', organization: 'ארגון וצוותים', expand: 'הרחבת התפריט', collapse: 'צמצום התפריט',
  expandSidebar: 'הרחבת סרגל הצד', collapseSidebar: 'צמצום סרגל הצד', active: 'מערכת פעילה',
  allDepartments: 'כל המחלקות', department: 'מחלקה', logout: 'יציאה', logoutPrompt: 'לצאת מהחשבון?', cancel: 'ביטול',
};
export function useNavigationText() { return useTranslation().locale === 'he' ? he : en; }

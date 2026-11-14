import { useTranslation } from './index';

const en = {
  title: 'Workflow reliability', window: 'Reliability time window', hours: '24 hours', week: '7 days', month: '30 days',
  failed: 'Workflow reliability could not be loaded.', completed: 'Completed', failures: 'Failed',
  trend: 'Workflow success and failure trend', totals: 'Workflows with runs', withFailures: 'With failures',
  empty: 'No completed or failed workflow runs in this window.', workflow: 'Workflow', failedRuns: 'Failed runs',
  failureRate: 'Failure rate', successRate: 'Success rate', duration: 'Avg. duration', cost: 'Avg. cost',
  diagnostics: 'Failure diagnostics', logs: 'Inspect last failed run', edit: 'Edit workflow',
  categories: {
    connector_auth: 'Connector authentication', budget: 'Budget', timeout: 'Timeout',
    output_validation: 'Output validation', unknown: 'Unknown',
  },
  suggestions: {
    connector_auth: 'Check connector credentials and resource grants in MCP Hub.',
    budget: 'Review department spending and budget policy in Org & Teams.',
    timeout: 'Review the timeout and consider splitting long work into parallel steps.',
    output_validation: 'Compare the step output with the expected response schema.',
    unknown: 'Inspect the latest failed run and its step events.',
  },
};
const he: typeof en = {
  title: 'אמינות תהליכי עבודה', window: 'טווח זמן למדדי אמינות', hours: '24 שעות', week: '7 ימים', month: '30 יום',
  failed: 'לא ניתן לטעון את מדדי האמינות.', completed: 'הושלמו', failures: 'נכשלו',
  trend: 'מגמת הצלחות וכשלים', totals: 'תהליכים שהורצו', withFailures: 'עם כשלים',
  empty: 'אין הרצות שהושלמו או נכשלו בטווח הזה.', workflow: 'תהליך עבודה', failedRuns: 'הרצות שנכשלו',
  failureRate: 'שיעור כשל', successRate: 'שיעור הצלחה', duration: 'משך ממוצע', cost: 'עלות ממוצעת',
  diagnostics: 'אבחון כשלים', logs: 'בדיקת ההרצה האחרונה שנכשלה', edit: 'עריכת תהליך',
  categories: {
    connector_auth: 'אימות מחבר', budget: 'תקציב', timeout: 'חריגה מזמן ההמתנה',
    output_validation: 'אימות פלט', unknown: 'לא ידוע',
  },
  suggestions: {
    connector_auth: 'יש לבדוק ב־MCP Hub את פרטי האימות של המחבר ואת הרשאות המשאבים.',
    budget: 'יש לבדוק את הוצאות המחלקה ואת מדיניות התקציב באזור ארגון וצוותים.',
    timeout: 'יש לבדוק את זמן ההמתנה ולשקול פיצול עבודה ממושכת לשלבים מקבילים.',
    output_validation: 'יש להשוות את פלט השלב לסכמת התגובה הצפויה.',
    unknown: 'יש לבדוק את ההרצה האחרונה שנכשלה ואת אירועי השלב.',
  },
};
export const useWorkflowMetricsText = () => useTranslation().locale === 'he' ? he : en;

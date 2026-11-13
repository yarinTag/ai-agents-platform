import { useTranslation } from './index';

const en = {
  title: 'Approvals inbox', workflow: 'Workflow', step: 'Paused step', expires: 'Expires',
  votes: 'Approvals', roles: 'Approver roles', review: 'Review evidence', approve: 'Approve', reject: 'Reject',
  close: 'Close', refresh: 'Refresh', previous: 'Previous', next: 'Next', empty: 'No pending approvals.',
  loadError: 'Could not load approvals.', decisionError: 'Decision could not be confirmed. Refresh and review the current state.',
  recorded: 'Decision recorded.', cost: 'Cost recorded so far', truncated: 'Excerpt', omitted: 'Additional outputs omitted',
  logs: 'Open execution logs', selectDepartment: 'Select a department to view its approvals.',
  waiting: 'Waiting for approval',
  barrier: 'Pause for human approval', timeout: 'Approval timeout in seconds', quorum: 'Required approvals',
  removeTools: 'Remove step tools and actions before converting this step to an approval.',
};
const he: typeof en = {
  title: 'תיבת אישורים', workflow: 'תהליך עבודה', step: 'שלב מושהה', expires: 'תפוגה',
  votes: 'אישורים', roles: 'תפקידי המאשרים', review: 'סקירת ראיות', approve: 'אישור', reject: 'דחייה',
  close: 'סגירה', refresh: 'רענון', previous: 'הקודם', next: 'הבא', empty: 'אין בקשות אישור ממתינות.',
  loadError: 'לא ניתן לטעון את האישורים.', decisionError: 'לא ניתן לאמת את ההחלטה. יש לרענן ולבדוק את המצב העדכני.',
  recorded: 'ההחלטה נשמרה.', cost: 'עלות שנרשמה עד כה', truncated: 'תקציר', omitted: 'תוצאות נוספות לא מוצגות',
  logs: 'פתיחת יומן ההרצה', selectDepartment: 'יש לבחור מחלקה כדי להציג את האישורים שלה.',
  waiting: 'ממתין לאישור',
  barrier: 'השהיה לאישור אנושי', timeout: 'זמן המתנה לאישור בשניות', quorum: 'מספר אישורים נדרש',
  removeTools: 'יש להסיר את הכלים והפעולות מהשלב לפני הפיכתו לשלב אישור.',
};
export const useDagApprovalsText = () => useTranslation().locale === 'he' ? he : en;

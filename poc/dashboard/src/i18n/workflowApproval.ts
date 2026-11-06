import { useTranslation } from './I18nContext';
const en = {
  title: 'Human approval', approve: 'Approve', approveMerge: 'Approve and merge reviewed PRs', reject: 'Reject',
  mergeHelp: 'Approval authorizes only the listed commits. The server rechecks current permissions, CI and PR state before merging. Changed or incomplete evidence blocks the action.',
  help: 'Review the report before deciding. Only an authorized department manager or organization admin can respond.',
  expires: 'Expires', report: 'Review report', confirm: 'Confirm this decision?', failed: 'Unable to load or resolve approval.',
  resolving: 'Decision is being processed. Do not repeat the request. If processing was interrupted, an administrator must reconcile the recorded receipts.',
};
const he: typeof en = {
  title: 'אישור אנושי', approve: 'אישור', approveMerge: 'אישור ומיזוג הבקשות שנבדקו', reject: 'דחייה',
  mergeHelp: 'האישור חל רק על הקומיטים המוצגים. השרת בודק שוב הרשאות, CI ומצב הבקשה לפני המיזוג. מידע שהשתנה או חסר חוסם את הפעולה.',
  help: 'יש לעיין בדוח לפני ההחלטה. רק מנהל מחלקה מורשה או מנהל הארגון יכולים להשיב.',
  expires: 'תוקף', report: 'דוח בדיקה', confirm: 'לאשר את ההחלטה?', failed: 'לא ניתן לטעון או לעדכן את האישור.',
  resolving: 'ההחלטה בעיבוד. אין לשלוח שוב. אם העיבוד נקטע, מנהל צריך לבדוק את תוצאות הפעולות שנרשמו.',
};
export function useWorkflowApprovalText() { return useTranslation().locale === 'he' ? he : en; }

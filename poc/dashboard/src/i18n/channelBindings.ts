import { useTranslation } from './index';

const en = {
  channelHeading: 'Channel',
  title: 'Channels', organization: 'Organization', department: 'Department', selectDepartment: 'Select a department to view its channels.',
  channel: 'Channel ID', connector: 'Connector', provider: 'Provider', status: 'Connector status', unknown: 'Unavailable',
  CONNECTED: 'Connected', CONNECTING: 'Connecting', DISCONNECTED: 'Disconnected', ERROR: 'Error',
  statusNote: 'Connector status does not verify access to this channel. Trigger and approval settings do not activate inbound handling.',
  readOnly: 'Organization administrators can manage channel bindings.', empty: 'No channels registered in this scope.',
  send_notifications: 'Send notifications', trigger_workflows: 'Trigger workflows', approve_decisions: 'Handle approvals',
  add: 'Add channel', edit: 'Edit uses', remove: 'Remove', confirmRemove: 'Remove this channel binding?',
  save: 'Save', cancel: 'Cancel', refresh: 'Refresh', more: 'Next page', previous: 'Previous page',
  loadError: 'Could not load channels.', connectorsError: 'Could not load connector details.',
  saveError: 'Could not confirm the change. Refresh the list before trying again.',
  conflict: 'The binding already exists or changed. The list has been refreshed.',
  required: 'Select a connector and one of its configured channels.',
  noConfiguredChannels: 'Configure an exact channel ID on a connector in the MCP Hub before registering it here.',
  notActive: 'Runtime unavailable',
};
const he: typeof en = {
  channelHeading: 'ערוץ',
  title: 'ערוצים', organization: 'ארגון', department: 'מחלקה', selectDepartment: 'יש לבחור מחלקה כדי לראות את הערוצים שלה.',
  channel: 'מזהה ערוץ', connector: 'מחבר', provider: 'ספק', status: 'מצב המחבר', unknown: 'לא זמין',
  CONNECTED: 'מחובר', CONNECTING: 'מתחבר', DISCONNECTED: 'מנותק', ERROR: 'שגיאה',
  statusNote: 'מצב המחבר אינו מאמת גישה לערוץ. הגדרות טריגרים ואישורים אינן מפעילות טיפול באירועים נכנסים.',
  readOnly: 'מנהלי הארגון יכולים לנהל רישומי ערוצים.', empty: 'אין ערוצים רשומים בהיקף זה.',
  send_notifications: 'שליחת התראות', trigger_workflows: 'הפעלת תהליכי עבודה', approve_decisions: 'טיפול באישורים',
  add: 'הוספת ערוץ', edit: 'עריכת שימושים', remove: 'הסרה', confirmRemove: 'להסיר את רישום הערוץ?',
  save: 'שמירה', cancel: 'ביטול', refresh: 'רענון', more: 'הדף הבא', previous: 'הדף הקודם',
  loadError: 'לא ניתן לטעון את הערוצים.', connectorsError: 'לא ניתן לטעון את פרטי המחברים.',
  saveError: 'לא ניתן לאמת את השינוי. יש לרענן את הרשימה לפני ניסיון נוסף.',
  conflict: 'הרישום כבר קיים או השתנה. הרשימה רועננה.',
  required: 'יש לבחור מחבר וערוץ שכבר מוגדר בו.',
  noConfiguredChannels: 'יש להגדיר מזהה ערוץ מדויק במחבר ב־MCP Hub לפני רישומו כאן.',
  notActive: 'לא זמין להפעלה',
};
export const useChannelBindingsText = () => useTranslation().dir === 'rtl' ? he : en;

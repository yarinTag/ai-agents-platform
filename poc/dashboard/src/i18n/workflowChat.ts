import { useTranslation } from './I18nContext';

const en = {
  title: 'Create a workflow with AI', entry: 'Create with AI',
  intro: 'Tell me what you want to happen. We’ll build it together.',
  placeholder: 'For example: review new issues in an allowed repository and send a summary to our team channel…',
  empty: 'What would you like to automate?',
  send: 'Send', stop: 'Stop', thinking: 'Working on your workflow…',
  preview: 'Your workflow', previewEmpty: 'Your steps will appear here as we build your workflow.',
  create: 'Create workflow', created: 'Created as inactive. Review it in Workflows before activating it.',
  inactive: 'Created inactive · nothing runs until you activate it',
  resources: 'Resources the assistant can use', repositories: 'Repositories', channels: 'Channel IDs', tools: 'Tools',
  available: 'Available', unavailable: 'Unavailable',
  department: 'Department', using: 'Using', you: 'You', assistant: 'Assistant',
  noDepartments: 'Ask your administrator for permission to create workflows in a department.',
  noModel: 'Choose a model in Runtime settings to get started.',
  noAgents: 'No execution agents are available. We can discuss your goal, but an administrator must assign agents before a workflow can be created.',
  missing: 'Only configured and permitted resources are shown. Ask your administrator to add anything missing.',
  connection: 'Connection interrupted. The server may be restarting. Please retry to reconnect.',
  timeout: 'The server did not respond in time. Your request may still be running; retry to reconnect.',
  httpError: 'The server returned HTTP {status}. Please retry.',
  error: 'Something went wrong. Please try again.', retry: 'Retry', newChat: 'Start over',
  schedule: 'Schedule', manual: 'Manual', delivery: 'Send results to', close: 'Close',
  invalid: 'A few details need attention before this workflow can be created.', settings: 'Runtime settings',
  example1: 'Summarize activity in a repository', example2: 'Review pull requests and notify my team',
};
const he: typeof en = {
  title: 'יצירת תהליך עבודה עם AI', entry: 'יצירה בעזרת AI',
  intro: 'ספרו לי מה תרצו שיקרה. נבנה את התהליך יחד.',
  placeholder: 'לדוגמה: לסקור סוגיות חדשות במאגר מורשה ולשלוח סיכום לערוץ הצוות…',
  empty: 'מה תרצו להפוך לאוטומטי?', send: 'שליחה', stop: 'עצירה', thinking: 'בונה את תהליך העבודה…',
  preview: 'תהליך העבודה שלכם', previewEmpty: 'שלבי התהליך יופיעו כאן במהלך השיחה.',
  create: 'יצירת תהליך עבודה', created: 'נוצר במצב לא פעיל. בדקו אותו במסך תהליכי העבודה לפני ההפעלה.',
  inactive: 'נוצר כלא פעיל · שום דבר לא ירוץ לפני הפעלה מפורשת',
  resources: 'המשאבים הזמינים לעוזר', repositories: 'מאגרים', channels: 'מזהי ערוצים', tools: 'כלים',
  available: 'זמין', unavailable: 'לא זמין',
  department: 'מחלקה', using: 'מודל', you: 'אתם', assistant: 'העוזר',
  noDepartments: 'בקשו מהמנהל הרשאה ליצור תהליכי עבודה במחלקה.',
  noModel: 'בחרו מודל בהגדרות ההפעלה כדי להתחיל.',
  noAgents: 'אין סוכני ביצוע זמינים. אפשר לתכנן את התהליך, אך מנהל צריך להקצות סוכנים לפני היצירה.',
  missing: 'מוצגים רק משאבים מוגדרים ומורשים. להוספת משאב חסר פנו למנהל.',
  connection: 'החיבור נותק. ייתכן שהשרת מופעל מחדש. נסו להתחבר שוב.',
  timeout: 'השרת לא הגיב בזמן. ייתכן שהבקשה עדיין פועלת; נסו להתחבר שוב.',
  httpError: 'השרת החזיר HTTP {status}. נסו שוב.',
  error: 'משהו השתבש. נסו שוב.', retry: 'ניסיון נוסף', newChat: 'התחלה מחדש',
  schedule: 'תזמון', manual: 'ידני', delivery: 'שליחת תוצאות אל', close: 'סגירה',
  invalid: 'יש פרטים שצריך לתקן לפני יצירת תהליך העבודה.', settings: 'הגדרות הפעלה',
  example1: 'סיכום פעילות במאגר', example2: 'סקירת בקשות מיזוג ועדכון הצוות',
};
export function useWorkflowChatText() {
  const { locale } = useTranslation();
  return locale === 'he' ? he : en;
}

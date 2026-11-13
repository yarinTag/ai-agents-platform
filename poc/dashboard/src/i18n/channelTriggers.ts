import { useTranslation } from './index';

const en = {
  title: 'Channel trigger', channel: 'Channel', matcher: 'Match by', pattern: 'Pattern', enabled: 'Enable trigger',
  parameter: 'Parameter name', source: 'Event field', add: 'Add parameter', remove: 'Remove parameter',
  event_type: 'Event type', command: 'Command', mention: 'Mention', keyword: 'Keyword', regex: 'Limited regex',
  channel_id: 'Channel ID', message_id: 'Message ID', sender_id: 'Sender ID', text: 'Message text',
  regexHint: 'Use literals, dot, or start and end anchors. Repetition and groups are unavailable.',
  sample: 'Sample message', preview: 'Preview', match: 'Matched', noMatch: 'No match', save: 'Save trigger',
  clear: 'Remove trigger', reload: 'Reload', empty: 'No channel trigger configured.',
  readOnly: 'You have read-only access.', unavailable: 'Could not load the trigger.',
  invalid: 'Check the trigger pattern, channel and parameter names.',
  conflict: 'The workflow changed. Reload before saving again.', saved: 'Trigger saved.',
  noBindings: 'No trigger-enabled channels are available in this department.',
  previewHint: 'Preview evaluates the rule only. It does not check a sender or start a workflow.',
};
const he: typeof en = {
  title: 'טריגר מערוץ', channel: 'ערוץ', matcher: 'התאמה לפי', pattern: 'תבנית', enabled: 'הפעלת טריגר',
  parameter: 'שם הפרמטר', source: 'שדה באירוע', add: 'הוספת פרמטר', remove: 'הסרת פרמטר',
  event_type: 'סוג אירוע', command: 'פקודה', mention: 'אזכור', keyword: 'מילת מפתח', regex: 'ביטוי רגולרי מוגבל',
  channel_id: 'מזהה ערוץ', message_id: 'מזהה הודעה', sender_id: 'מזהה שולח', text: 'טקסט ההודעה',
  regexHint: 'אפשר להשתמש בתווים רגילים, בנקודה ובעוגני התחלה וסוף. חזרות וקבוצות אינן נתמכות.',
  sample: 'הודעה לדוגמה', preview: 'תצוגה מקדימה', match: 'נמצאה התאמה', noMatch: 'אין התאמה', save: 'שמירת טריגר',
  clear: 'הסרת טריגר', reload: 'טעינה מחדש', empty: 'לא הוגדר טריגר מערוץ.',
  readOnly: 'יש לך הרשאת צפייה בלבד.', unavailable: 'לא ניתן לטעון את הטריגר.',
  invalid: 'יש לבדוק את התבנית, הערוץ ושמות הפרמטרים.',
  conflict: 'ה־workflow השתנה. יש לטעון מחדש לפני שמירה.', saved: 'הטריגר נשמר.',
  noBindings: 'אין במחלקה ערוצים זמינים שמוגדרים לטריגרים.',
  previewHint: 'התצוגה בודקת את הכלל בלבד. היא אינה מאמתת שולח או מפעילה workflow.',
};
export const useChannelTriggersText = () => useTranslation().locale === 'he' ? he : en;

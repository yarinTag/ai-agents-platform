import { useTranslation } from './index';

const en = {
  destination: 'Approval destination', dashboard: 'Dashboard only', preview: 'Telegram card preview',
  sample: 'Sample only. The deadline starts when the workflow pauses.',
  summary: 'Include findings from a preceding step', findings: 'Findings from',
  fallback: 'Approvers can use the Approvals inbox if Telegram is unavailable.',
  unavailable: 'This saved channel is unavailable for approvals. Check its department binding.',
  loadError: 'Could not load department channels.', details: 'Dashboard details link is optional.',
  missingHttps: 'Configure the public HTTPS ingress endpoint for Telegram callbacks.',
  missingSecret: 'An administrator must configure the Telegram webhook secret.',
  unknown: 'An organization administrator can check HTTPS and webhook secrets in MCP Hub.',
  linked: 'Your Telegram identity is linked.', unlinked: 'Link your Telegram identity before deciding from chat.',
  unknownIdentity: 'Could not verify your linked identity.',
  support: 'Interactive cards are available for Telegram. Enable both Send and Approve on the department channel.',
  remove: 'Remove the approval checkpoint?', source: 'Decision source', dashboardSource: 'Dashboard', telegram: 'Telegram', refreshed: 'Approval records refresh automatically.',
};
const he: typeof en = {
  destination: 'יעד האישור', dashboard: 'דשבורד בלבד', preview: 'תצוגה מקדימה של כרטיס Telegram',
  sample: 'דוגמה בלבד. הספירה מתחילה כשהתהליך מושהה.',
  summary: 'צירוף ממצאים משלב קודם', findings: 'ממצאים מתוך',
  fallback: 'אפשר לאשר דרך תיבת האישורים כש־Telegram אינו זמין.',
  unavailable: 'הערוץ השמור אינו זמין לאישורים. יש לבדוק את הגדרת הערוץ במחלקה.',
  loadError: 'לא ניתן לטעון את ערוצי המחלקה.', details: 'הקישור לפרטים בדשבורד הוא אופציונלי.',
  missingHttps: 'יש להגדיר כתובת HTTPS ציבורית לקבלת פעולות מ־Telegram.',
  missingSecret: 'מנהל ארגון צריך להגדיר סוד webhook ל־Telegram.',
  unknown: 'מנהל ארגון יכול לבדוק את כתובת HTTPS ואת סוד ה־webhook ב־MCP Hub.',
  linked: 'חשבון Telegram שלך מקושר.', unlinked: 'יש לקשר חשבון Telegram לפני אישור מתוך הערוץ.',
  unknownIdentity: 'לא ניתן לבדוק את קישור החשבון.',
  support: 'כרטיסים אינטראקטיביים זמינים ב־Telegram. יש להפעיל שליחה ואישור בערוץ המחלקתי.',
  remove: 'להסיר את שלב האישור?', source: 'מקור ההחלטה', dashboardSource: 'דשבורד', telegram: 'Telegram', refreshed: 'רשומות האישורים מתרעננות אוטומטית.',
};
export function useChannelApprovalsText() {
  return useTranslation().locale === 'he' ? he : en;
}

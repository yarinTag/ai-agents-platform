import { useTranslation } from './I18nContext';

const en = {
  advanced: 'Advanced execution parameters (optional)',
  deliveryWarning: 'Summary may complete, but notification delivery is blocked',
  mode: 'Run location', local: 'Run on this server', queue: 'Send to message queue',
  help: 'Local execution needs no message broker. It runs real workflow steps and stops if this server restarts. Queued execution requires a connected broker and worker. Neither mode changes agent tools or permissions.',
  queueUnavailable: 'The message queue is unavailable. Choose “Run on this server” or restore the broker and worker.',
  capabilityUnavailable: 'The {name} service is unavailable. Check the backend service status.',
  failed: 'Workflow execution could not be started.',
};
const he: typeof en = {
  advanced: 'פרמטרים מתקדמים להרצה (אופציונלי)',
  deliveryWarning: 'אפשר להשלים את הסיכום, אך שליחת ההודעה חסומה',
  mode: 'מיקום ההרצה', local: 'הרצה בשרת הזה', queue: 'שליחה לתור ההודעות',
  help: 'הרצה מקומית אינה דורשת שירות תורים. היא מפעילה את שלבי התהליך ונפסקת אם השרת מופעל מחדש. הרצה בתור דורשת שירות תורים וצרכן פעילים. שתי האפשרויות שומרות על כלי הסוכן והרשאותיו.',
  queueUnavailable: 'תור ההודעות אינו זמין. בחרו בהרצה בשרת הזה או שחזרו את שירות התורים והצרכן.',
  capabilityUnavailable: 'השירות {name} אינו זמין. בדקו את מצב שירותי השרת.',
  failed: 'לא ניתן להתחיל את תהליך העבודה.',
};
export function useWorkflowRunText() {
  const { locale } = useTranslation();
  return locale === 'he' ? he : en;
}

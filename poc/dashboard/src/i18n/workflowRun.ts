import { useTranslation } from './I18nContext';

const en = {
  noEvents: 'No runtime events captured for this step.', more: 'More', less: 'Less', hideJson: 'Hide JSON',
  back: 'Back to Workflows', workflow: 'Workflow', logs: 'Execution Logs', refresh: 'Refresh',
  loadFailed: 'Unable to load logs', history: 'Runs History', allRuns: 'All Runs', live: 'Live', playground: 'Playground',
  noRuns: 'No runs match the current filter.', chooseRun: 'Select a run to inspect its logs.', exportJson: 'Export JSON',
  started: 'Started', finished: 'Finished', pending: 'Pending', durationCost: 'Duration & cost', tokens: 'Tokens (in / out)',
  runFailed: 'Run failed', payload: 'Run Input Payload', search: 'Search step output, input, and runtime events…',
  waitingFirst: 'Waiting for the first step', noSteps: 'No step logs were recorded',
  beforeStep: 'This run failed before a step started, or predates step logging. See the run error above.',
  reasoning: 'Reasoning', sessionTotal: 'Session total', stepFailed: 'Step failed', output: 'Step Output',
  running: 'Running…', noOutput: 'No output', input: 'Step Input', events: 'Runtime Events',
  logsRefresh: 'Run history, step output, and runtime diagnostics. Active runs refresh every 10 seconds.',
  advanced: 'Advanced execution parameters (optional)',
  deliveryWarning: 'Summary may complete, but notification delivery is blocked',
  mode: 'Run location', local: 'Run on this server', queue: 'Send to message queue',
  help: 'Local execution needs no message broker. It runs real workflow steps and stops if this server restarts. Queued execution requires a connected broker and worker. Neither mode changes agent tools or permissions.',
  queueUnavailable: 'The message queue is unavailable. Choose “Run on this server” or restore the broker and worker.',
  capabilityUnavailable: 'The {name} service is unavailable. Check the backend service status.',
  failed: 'Workflow execution could not be started.',
};
const he: typeof en = {
  noEvents: 'לא נרשמו אירועי הרצה לשלב הזה.', more: 'הרחבה', less: 'צמצום', hideJson: 'הסתרת JSON',
  back: 'חזרה לתהליכי העבודה', workflow: 'תהליך עבודה', logs: 'יומני הרצה', refresh: 'רענון',
  loadFailed: 'לא ניתן לטעון את היומנים', history: 'היסטוריית הרצות', allRuns: 'כל ההרצות', live: 'בפועל', playground: 'סביבת תרגול',
  noRuns: 'אין הרצות התואמות למסנן.', chooseRun: 'בחרו הרצה כדי לעיין ביומנים שלה.', exportJson: 'ייצוא JSON',
  started: 'התחלה', finished: 'סיום', pending: 'ממתין', durationCost: 'משך ועלות', tokens: 'טוקנים (קלט / פלט)',
  runFailed: 'ההרצה נכשלה', payload: 'נתוני קלט להרצה', search: 'חיפוש בפלט השלבים, בקלט ובאירועי ההרצה…',
  waitingFirst: 'ממתין לשלב הראשון', noSteps: 'לא נרשמו יומני שלבים',
  beforeStep: 'ההרצה נכשלה לפני תחילת שלב, או קדמה לתיעוד השלבים. בדקו את שגיאת ההרצה למעלה.',
  reasoning: 'נימוק המודל', sessionTotal: 'עלות השיחה הכוללת', stepFailed: 'השלב נכשל', output: 'פלט השלב',
  running: 'בהרצה…', noOutput: 'אין פלט', input: 'קלט השלב', events: 'אירועי הרצה',
  logsRefresh: 'היסטוריית הרצות, פלט שלבים ואבחון. הרצות פעילות מתעדכנות כל 10 שניות.',
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

import { useTranslation } from './I18nContext';
const en = {
  findChats: 'Find chats',
  sendTest: 'Send test message',
  connectionTest: 'Check connection',
  testHint: 'Save the destination first, then send a test from the installed integration.',
  findHint: 'Look up chats recently visible to this bot. Choose the intended ID and save it; no message is sent.',
  telegramPlaceholder: 'Numeric chat ID or public @channel username',
  availableChats: 'Available chat IDs — choose the intended chat:',
  availableSlack: 'Configured Slack channel IDs:',
  invalidTarget: 'Use a real numeric Telegram chat ID or @channel username, or a Slack channel ID. Display names cannot be used for delivery.',
};
const he: typeof en = {
  findChats: 'איתור שיחות',
  sendTest: 'שליחת הודעת בדיקה',
  connectionTest: 'בדיקת חיבור',
  testHint: 'שמרו את היעד ואז שלחו הודעת בדיקה מהחיבור המותקן.',
  findHint: 'חיפוש שיחות שנראו לאחרונה לבוט. בחרו ושמרו את המזהה הרצוי; לא תישלח הודעה.',
  telegramPlaceholder: 'מזהה שיחה מספרי או שם ערוץ ציבורי עם @',
  availableChats: 'מזהי שיחות זמינים — בחרו את השיחה הרצויה:',
  availableSlack: 'מזהי ערוצי Slack מוגדרים:',
  invalidTarget: 'השתמשו במזהה שיחה מספרי של Telegram, בשם ערוץ עם @ או במזהה ערוץ Slack. שם תצוגה אינו יעד לשליחה.',
};
export function useConnectorResourceText() {
  const { locale } = useTranslation();
  return locale === 'he' ? he : en;
}

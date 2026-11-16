import { useTranslation } from './index';

const en = {
  title: 'Run audit timeline', run: 'Workflow run', ingress: 'Verified channel event',
  principal: 'Execution principal', sender: 'Linked sender', revision: 'Workflow revision',
  approval: 'Human approval', delivery: 'Card delivery', actor: 'Decision actor', receipt: 'Connector receipt',
  unknown: 'Delivery unconfirmed. Check the channel before taking further action.',
  inspect: 'Open MCP Hub', review: 'Open approvals', truncated: 'Showing the latest 100 connector receipts.',
  telegram: 'Telegram', dashboard: 'Dashboard',
};
const he: typeof en = {
  title: 'ציר זמן לביקורת ההרצה', run: 'הרצת תהליך', ingress: 'אירוע ערוץ מאומת',
  principal: 'זהות ההרצה', sender: 'שולח מקושר', revision: 'גרסת התהליך',
  approval: 'אישור אנושי', delivery: 'מסירת כרטיס', actor: 'מחליט', receipt: 'אסמכתת מחבר',
  unknown: 'המסירה לא אומתה. יש לבדוק את הערוץ לפני פעולה נוספת.',
  inspect: 'פתיחת MCP Hub', review: 'פתיחת אישורים', truncated: 'מוצגות 100 אסמכתאות המחברים האחרונות.',
  telegram: 'Telegram', dashboard: 'דשבורד',
};
export const useRunAuditText = () => useTranslation().locale === 'he' ? he : en;

import { useTranslation } from './index';

const en = {
  scope: 'Plugin source scope', organization: 'Organization', department: 'Department',
  inherited: 'Plugin source inherited from', departmentSource: 'Department plugin source',
  repository: 'Department GitHub repository', save: 'Save repository', inherit: 'Use inherited source', refresh: 'Refresh',
};
const he: typeof en = {
  scope: 'תחום מקור התוספים', organization: 'ארגון', department: 'מחלקה',
  inherited: 'מקור תוספים בירושה מ־', departmentSource: 'מקור תוספים מחלקתי',
  repository: 'מאגר GitHub מחלקתי', save: 'שמירת מאגר', inherit: 'שימוש במקור בירושה', refresh: 'רענון',
};
export const usePluginSourceText = () => useTranslation().locale === 'he' ? he : en;

import { useTranslation } from './I18nContext';

const en = {
  title: 'Workflows & Automations Hub', subtitle: 'Multi-agent DAG orchestration, automated triggers, and smart execution deduplication.',
  refresh: 'Refresh', create: 'Create Workflow', total: 'Total workflows', activePipelines: 'Active pipelines', queued: 'Queued runs', deduplicated: 'Deduplicated runs',
  playbooks: 'Playbooks & Pipelines', executionHistory: 'Execution History & Queue',
  playground: 'Playground', execute: 'Execute Workflow', runPlayground: 'Run in Playground', launch: 'Launch Execution', cancel: 'Cancel',
  exercise: 'Tool-free workflow exercise', exerciseHelp: 'Runs the same DAG with real model calls and normal token costs. MCP, file and shell tools, channel notifications, and external approvals are disabled. Supply all required data in the JSON input. Each run starts fresh; results may differ from workflows using live tools.',
  payload: 'Execution Trigger Payload (JSON)', payloadHelp: 'Custom input variables passed to workflow steps as {{variable_name}}',
  forceRerun: 'Force Re-run', forceHelp: 'Bypass deduplication and caching, forcing all agents to execute from scratch', force: 'Force', cached: 'Cached',
  canvas: 'Workflow DAG Canvas', definition: 'Playbook Definition', copy: 'Copy', close: 'Close',
  name: 'Workflow Name', department: 'Department', global: 'Global', triggers: 'Triggers & Bindings',
  cron: 'Cron schedule', webhookHelp: 'Webhook enabled. Click to copy webhook token.', webhookToken: 'Webhook Token', manual: 'Manual Trigger Only',
  steps: 'Steps', stages: 'DAG execution stages', status: 'Status', active: 'Active', inactive: 'Inactive', actions: 'Actions', run: 'Run',
  actionsFor: 'Actions for workflow', edit: 'Edit', history: 'History', logs: 'Logs', canvasAction: 'Canvas', definitionAction: 'YAML / JSON Definition',
  delete: 'Delete', deletePrompt: 'Delete this workflow?', deleteHelp: 'This will permanently delete this playbook and its configuration.', deleteConfirm: 'Yes, Delete',
  executionId: 'Execution ID', workflow: 'Workflow', trigger: 'Trigger', cachedRun: 'Deduplicated / cached', tokensCost: 'Tokens & Cost', tokens: 'tokens', created: 'Created At', inspect: 'Inspect',
};
const he: typeof en = {
  title: 'מרכז תהליכי עבודה ואוטומציות', subtitle: 'תזמור סוכנים בתרשים תלויות, טריגרים אוטומטיים ומניעת הרצות כפולות.',
  refresh: 'רענון', create: 'יצירת תהליך עבודה', total: 'סך תהליכי העבודה', activePipelines: 'תהליכים פעילים', queued: 'הרצות בתור', deduplicated: 'הרצות כפולות שנמנעו',
  playbooks: 'תהליכי עבודה', executionHistory: 'היסטוריית הרצות ותור',
  playground: 'סביבת תרגול', execute: 'הרצת תהליך עבודה', runPlayground: 'הרצה בסביבת תרגול', launch: 'התחלת הרצה', cancel: 'ביטול',
  exercise: 'תרגול תהליך ללא כלים', exerciseHelp: 'מריץ את אותו תרשים עם קריאות מודל אמיתיות ועלות טוקנים רגילה. כלי MCP, קבצים ומעטפת, הודעות לערוצים ואישורים חיצוניים מושבתים. יש לספק את כל הנתונים בקלט JSON. כל הרצה מתחילה מחדש והתוצאות עשויות להיות שונות מהרצה עם כלים חיים.',
  payload: 'נתוני קלט להרצה (JSON)', payloadHelp: 'משתני קלט המועברים לשלבים בתבנית {{variable_name}}',
  forceRerun: 'הרצה מחדש בכפייה', forceHelp: 'מדלג על מניעת כפילויות ועל המטמון ומריץ את כל הסוכנים מההתחלה', force: 'בכפייה', cached: 'מטמון',
  canvas: 'תרשים תלויות התהליך', definition: 'הגדרת התהליך', copy: 'העתקה', close: 'סגירה',
  name: 'שם התהליך', department: 'מחלקה', global: 'כללי', triggers: 'טריגרים וקישורים',
  cron: 'תזמון Cron', webhookHelp: 'Webhook פעיל. לחצו להעתקת אסימון ה־Webhook.', webhookToken: 'אסימון Webhook', manual: 'טריגר ידני בלבד',
  steps: 'שלבים', stages: 'שלבי הרצה בתרשים', status: 'סטטוס', active: 'פעיל', inactive: 'לא פעיל', actions: 'פעולות', run: 'הרצה',
  actionsFor: 'פעולות לתהליך', edit: 'עריכה', history: 'היסטוריה', logs: 'יומנים', canvasAction: 'תרשים', definitionAction: 'הגדרת YAML / JSON',
  delete: 'מחיקה', deletePrompt: 'למחוק את התהליך?', deleteHelp: 'הפעולה תמחק לצמיתות את התהליך והגדרותיו.', deleteConfirm: 'כן, למחוק',
  executionId: 'מזהה הרצה', workflow: 'תהליך עבודה', trigger: 'טריגר', cachedRun: 'כפילות שנמנעה / מטמון', tokensCost: 'טוקנים ועלות', tokens: 'טוקנים', created: 'מועד יצירה', inspect: 'עיון',
};
export type WorkflowHubText = typeof en;
export function useWorkflowHubText() { return useTranslation().locale === 'he' ? he : en; }

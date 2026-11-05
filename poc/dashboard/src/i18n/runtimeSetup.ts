import { useTranslation } from './I18nContext';

const en = {
    "messageThreads": "Enable Anthropic Message Threads (beta)",
    "messageThreadsHelp": "Smaller requests for active conversations; token prices stay unchanged. Anthropic temporarily retains conversation state. Not eligible for ZDR or HIPAA.",
    "title": "Organization API Providers & Models",
    "intro": "Select the active API provider(s) and default model for agents and workflows. Available models across the platform automatically adapt to the providers you configure here.",
    "credentials": "Each organization uses its own encrypted API keys. Only organization administrators can replace or revoke them. Server-wide keys are never used as a fallback.",
    "adminOnly": "Only an organization administrator can manage these settings.",
    "revoke": "Revoke key",
    "revokeConfirm": "Revoke this organization's key? New model requests will be blocked.",
    "apiKey": "API Key",
    "apiKeyConfiguredPlaceholder": "API key already configured for this organization (enter a new key to override)",
    "apiKeyMissingPlaceholder": "Enter provider API key (e.g. nvapi-..., sk-...)...",
    "enableModels": "Include this provider's models in model selectors",
    "model": "Default Provider Model",
    "modelPlaceholder": "Select or type a model ID for this provider",
    "modelHelp": "Used when an agent is set to 'Default' or a capability tier. You can pick from the curated list or type any model ID supported by this provider.",
    "settings": "Runtime settings",
    "loadError": "Could not load runtime settings."
};

const he: typeof en = {
    "messageThreads": "הפעלת Anthropic Message Threads (בטא)",
    "messageThreadsHelp": "בקשות קטנות יותר בשיחות פעילות; מחיר הטוקנים אינו משתנה. Anthropic שומרת זמנית את מצב השיחה. לא מתאים ל־ZDR או HIPAA.",
    "title": "ספקי API ומודלים של הארגון",
    "intro": "בחרו את ספקי ה־API הפעילים ואת מודל ברירת המחדל עבור סוכנים ותהליכי עבודה. רשימת המודלים בפלטפורמה מתעדכנת אוטומטית לפי הספקים שהגדרתם.",
    "credentials": "לכל ארגון מפתחות API משלו, הנשמרים מוצפנים. רק מנהלי הארגון יכולים להחליף או לבטל אותם. אין שימוש במפתחות גלובליים כגיבוי.",
    "adminOnly": "רק מנהל הארגון יכול לשנות את ההגדרות האלה.",
    "revoke": "ביטול מפתח",
    "revokeConfirm": "לבטל את מפתח הארגון? קריאות מודל חדשות ייחסמו.",
    "apiKey": "מפתח API",
    "apiKeyConfiguredPlaceholder": "מפתח API כבר מוגדר לארגון (הזינו מפתח חדש כדי לדרוס)",
    "apiKeyMissingPlaceholder": "הזינו מפתח API של הספק...",
    "enableModels": "הצג את המודלים של ספק זה בבוררי המודלים",
    "model": "מודל ברירת מחדל לספק",
    "modelPlaceholder": "בחרו או הקלידו מזהה מודל עבור ספק זה",
    "modelHelp": "משמש כאשר סוכן מוגדר ל־Default או לרמת יכולת. ניתן לבחור מהרשימה או להקליד כל מזהה מודל הנתמך על ידי הספק.",
    "settings": "הגדרות הפעלה",
    "loadError": "לא ניתן לטעון הגדרות הפעלה."
};

export function useRuntimeSetupText() {
  const { locale } = useTranslation();
  return locale === 'he' ? he : en;
}

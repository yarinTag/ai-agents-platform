import { useTranslation } from './I18nContext';

const en = {
    "title": "Configure AI API Providers & Models",
    "intro": "Select the active API provider(s) and default model for agents and workflows. Available models across the platform automatically adapt to the providers you configure here.",
    "credentials": "API keys are stored securely on the platform server. You can use environment variables or enter an API key directly below.",
    "apiKey": "API Key",
    "apiKeyConfiguredPlaceholder": "API key already configured on server (enter a new key to override)",
    "apiKeyMissingPlaceholder": "Enter provider API key (e.g. nvapi-..., sk-...)...",
    "enableModels": "Include this provider's models in model selectors",
    "model": "Default Provider Model",
    "modelPlaceholder": "Select or type a model ID for this provider",
    "modelHelp": "Used when an agent is set to 'Default' or a capability tier. You can pick from the curated list or type any model ID supported by this provider.",
    "settings": "Runtime settings",
    "loadError": "Could not load runtime settings."
};

const he: typeof en = {
    "title": "הגדרת ספקי API ומודלים",
    "intro": "בחרו את ספקי ה־API הפעילים ואת מודל ברירת המחדל עבור סוכנים ותהליכי עבודה. רשימת המודלים בפלטפורמה מתעדכנת אוטומטית לפי הספקים שהגדרתם.",
    "credentials": "מפתחות ה־API נשמרים בשרת הפלטפורמה. ניתן להשתמש במשתני סביבה או להזין מפתח API ישירות למטה.",
    "apiKey": "מפתח API",
    "apiKeyConfiguredPlaceholder": "מפתח API כבר מוגדר בשרת (הזינו מפתח חדש כדי לדרוס)",
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

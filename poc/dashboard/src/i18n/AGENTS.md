# AGENTS.md - Internationalization (i18n) Engine

## 1. Overview & Directory Mission
The `src/i18n/` directory provides type-safe, lightweight internationalization for the AI Agents Platform Dashboard. It is built natively without third-party runtime bloat, supporting English as the default primary language while providing complete infrastructure and dictionaries for bidirectional RTL Hebrew localization.

---

## 2. Architecture & File Structure

```
poc/dashboard/src/i18n/
├── AGENTS.md            # This documentation file
├── I18nContext.tsx      # Context provider, state management, and useTranslation hook
├── index.ts             # Public barrel export
└── locales/
    ├── en.ts            # Canonical English translation dictionary (default)
    └── he.ts            # Complete Hebrew translation dictionary (RTL)
```

---

## 3. Core Capabilities & Mechanics

### 3.1 English Default UI Invariant
* **Invariant**: The application MUST default to `'en'` (English).
* The active locale is persisted in `localStorage` under key `'i18n_locale'`. If no saved preference exists, it strictly resolves to `'en'`.
* **Zero Hardcoded Hebrew in Components**: Developers and agents must NEVER write raw Hebrew text strings directly in JSX elements. All copy must be defined in English in the JSX or referenced via `t('key')`.

### 3.2 Type-Safe Translation Dictionary Contract
* The TypeScript type `TranslationDictionary` is derived directly from [`src/i18n/locales/en.ts`](file:///Users/yarintag/Desktop/Projects/ai-agents-platform/poc/dashboard/src/i18n/locales/en.ts):
  ```typescript
  export type TranslationDictionary = typeof en;
  ```
* [`src/i18n/locales/he.ts`](file:///Users/yarintag/Desktop/Projects/ai-agents-platform/poc/dashboard/src/i18n/locales/he.ts) implements `TranslationDictionary`, ensuring full 1:1 key parity at compile time.

### 3.3 Safe Key Resolution & Interpolation
* The `t()` function safely navigates nested objects using dot notation (e.g. `t('org.departments')` or `t('common.save')`).
* If a key is missing in Hebrew, it automatically falls back to the English dictionary before falling back to an optional fallback string or the raw key.
* Parameter interpolation replaces `{paramName}` tokens:
  ```typescript
  t('org.memberCount', { count: 5 }); // Returns "5 Members"
  ```

### 3.4 Bidirectional Layout (LTR / RTL)
* `I18nContext` provides:
  * `locale`: `'en' | 'he'`
  * `setLocale`: `(locale: Locale) => void`
  * `dir`: `'ltr' | 'rtl'`
  * `isRtl`: `boolean`
* When switching to `'he'`, document `dir` is updated and Ant Design adjusts layout direction accordingly.

---

## 4. Usage Pattern

```tsx
import React from 'react';
import { useTranslation } from '../i18n';

export const MyComponent: React.FC = () => {
  const { t, locale, setLocale, isRtl } = useTranslation();

  return (
    <div>
      <h2>{t('common.dashboard')}</h2>
      <button onClick={() => setLocale(locale === 'en' ? 'he' : 'en')}>
        {t('common.switchLang')}
      </button>
    </div>
  );
};
```

---

## 5. 🔄 Mandatory UI `AGENTS.md` Synchronization Rule

### Feature availability copy

Both dictionaries define `featureAvailability`: unavailable, renderFailure, navigationAvailable, retry, checking, reportUnavailable, degraded, configureLater. Route error/capability panels and optional runtime setup use these keys. The availability-report warning explains that its failure does not prevent trying the view; no raw exception text is rendered. `configureLater` allows dismissing first-run runtime selection so unavailable providers do not prevent unrelated administration. No change to locale persistence, fallback lookup or document RTL handling is introduced.

> [!IMPORTANT]
> **Every time any file in `src/i18n/` is added, modified, or refactored, the developer/agent MUST update this file (`src/i18n/AGENTS.md`) as part of the same task.**
>
> Mandatory Rules:
> 1. When adding a new string to [`locales/en.ts`](file:///Users/yarintag/Desktop/Projects/ai-agents-platform/poc/dashboard/src/i18n/locales/en.ts), you MUST simultaneously add the corresponding Hebrew translation to [`locales/he.ts`](file:///Users/yarintag/Desktop/Projects/ai-agents-platform/poc/dashboard/src/i18n/locales/he.ts).
> 2. NEVER introduce hardcoded Hebrew strings into UI components or pages.
> 3. Document any new translation domains or context helper utilities in this file.

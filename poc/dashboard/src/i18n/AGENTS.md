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

## Runtime setup copy
`runtimeSetup.ts` exports `useRuntimeSetupText` and aligned typed English/Hebrew setup dictionaries for Direct API provider selection, API key configuration, multi-provider model enabling (`enableModels`), and per-provider default model selection. The `assistant.*` dictionary section in `en.ts` and `he.ts` was removed on 2026-10-31 alongside Workflow Assistant.

## Friendly workflow chat copy
workflowChat.ts exports useWorkflowChatText with aligned typed English/Hebrew domain dictionaries. It covers Create with AI, example prompts, conversation/preview, configured-model/runtime settings, resource categories/missing access, generation/stop/retry and inactive creation. It reads the existing locale context and does not modify the large legacy dictionaries or locale persistence.

Workflow chat EN/HE also distinguishes connection loss, server timeout and HTTP status errors. Successful reconnects clear transient banners without clearing real model errors.

workflowRun.ts adds aligned EN/HE copy for explicit local/queued execution, restart durability limits, queue outages and structured capability errors. It uses the existing locale context.

workflowChat.ts adds typed EN/HE available/unavailable resource status labels; backend identifiers and runtime policy errors remain server data.

workflowRun EN/HE adds the separate optional-delivery warning label for execution inspection/logs.

`connectorResources.ts` owns English/Hebrew chat-ID discovery labels, target input guidance and invalid delivery-target validation messages.

connectorResources also supplies Find chats, Send test message, Check connection and save-before-testing guidance in English/Hebrew.

workflowChat supplies the plugin-skills resource label in English/Hebrew.

workflowChat includes Workflow Skills and inheritance/direct-action guidance in English/Hebrew, shared by the builder and AI preview.

workflowChat plannedRunner describes dedicated workflow runner provisioning on confirmation in English/Hebrew.

## Workflow settings copy
`workflowSettings.ts` exports `useWorkflowSettingsText`, the `WorkflowSettingsText` type, and `formatWorkflowSettingsText(template, params)` for `{name}`-style placeholders. It holds typed English/Hebrew dictionaries (Hebrew is `typeof en`, so keys stay in parity) for the Workflows **Settings** action, the settings drawer (model/tiers/catalog, machine size, network allowlist, save/409 conflict/validation/permission messages, read-only and invalid-settings notices) and the secrets section (table, add/replace form, name/value/ARN validation, 503 storage-not-configured). It reads the existing locale context; the legacy `en.ts`/`he.ts` dictionaries are unchanged. Server-provided details (validation text, tier/model names) are shown as returned.


workflowChat.ts adds matching EN/HE workspace, draftPr and readWorkspace labels for typed repository workspace previews and permission catalog display. No locale-state changes or runtime verification.


workflowChat EN/HE adds executionMode, connectorMode, workspaceConnector, workspaceRef, workspacePrTitle, workspacePermissionHint, workspaceCatalogError, workspaceIsolation and workspaceSetupRequired for manual workspace editing and readiness warnings. No tests or build performed.


workflowChat EN/HE adds notifyEachStep, notifyStartComplete, notifyCompletion and notifyNone labels, shared by Channel Binding mode selection and AI preview. No locale changes or runtime checks.


Notification cadence labels simplified in matching EN/HE: Every step / בכל שלב; Start and finish / בתחילה ובסיום; Finish only / בסיום בלבד; Off / כבוי. Shared labels also update AI preview. No runtime checks performed.

RuntimeSetup EN/HE copy now describes encrypted organization-owned provider keys without global/environment fallback and adds adminOnly, revoke, revokeConfirm. No runtime checks performed.

workflowSettings.ts adds EN/HE backendSection/backendHelp/backendPending/backendBlocked/backendBlockedHelp for the execution-engine control and explicit pending-runtime warning. No build/typecheck/UI execution.

workflowSettings adds EN/HE backendSetupNeeded and updates backendBlockedHelp to distinguish server configuration from unsupported engines and describe the read-only SDK limit. No runtime checks.

runtimeSetup.ts adds matched EN/HE messageThreads/messageThreadsHelp labels describing opt-in, unchanged token prices, temporary provider retention and ZDR/HIPAA incompatibility. No runtime verification performed.

## Organization Workflows Canvas copy (2026-11-03)
`orgWorkflowsCanvas.ts` exports `useOrgWorkflowsCanvasText` and `OrgWorkflowsCanvasText` with aligned English (`en`) and Hebrew (`he`) translations for the Organization & Department Workflows Canvas tab, filters, topology legend, triggers, expandable DAG stages, external resource/channel connections, and the workflow inspector drawer.

workflowChat.noDepartments EN/HE now explains department membership rather than a manager-only workflow creation permission. No local runtime verification performed.


workflowApproval.ts supplies matched EN/HE human decision labels, merge authorization/expiry/unknown-outcome copy. workflowChat adds humanApproval/mergeAfterApproval preview labels.

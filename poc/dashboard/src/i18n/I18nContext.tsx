import React, { createContext, useContext, useState, useEffect, useCallback, useMemo } from 'react';
import { en, TranslationDictionary } from './locales/en';
import { he } from './locales/he';

export type Locale = 'en' | 'he';

export interface I18nContextType {
  locale: Locale;
  setLocale: (locale: Locale) => void;
  t: (key: string, paramsOrFallback?: Record<string, string | number> | string, fallback?: string) => string;
  dir: 'ltr' | 'rtl';
  isRtl: boolean;
}

const dictionaries: Record<Locale, TranslationDictionary> = {
  en,
  he,
};

const LOCALE_STORAGE_KEY = 'i18n_locale';

// Helper function to resolve dot-notated paths safely
const resolveKey = (dict: any, path: string): string | undefined => {
  if (!dict || !path) return undefined;
  const parts = path.split('.');
  let current: any = dict;
  for (const part of parts) {
    if (current && typeof current === 'object' && part in current) {
      current = current[part];
    } else {
      return undefined;
    }
  }
  return typeof current === 'string' ? current : undefined;
};

// Safe fallback translate implementation
const createTranslate = (currentLocale: Locale) => {
  return (
    key: string,
    paramsOrFallback?: Record<string, string | number> | string,
    fallback?: string
  ): string => {
    let rawText = resolveKey(dictionaries[currentLocale], key);
    if (!rawText && currentLocale !== 'en') {
      // Fallback to English
      rawText = resolveKey(dictionaries.en, key);
    }

    let defaultFallback = '';
    let params: Record<string, string | number> | undefined;

    if (typeof paramsOrFallback === 'string') {
      defaultFallback = paramsOrFallback;
    } else if (paramsOrFallback && typeof paramsOrFallback === 'object') {
      params = paramsOrFallback;
      defaultFallback = fallback || '';
    } else if (fallback) {
      defaultFallback = fallback;
    }

    let result = rawText !== undefined ? rawText : defaultFallback || key;

    if (params) {
      for (const [paramKey, paramVal] of Object.entries(params)) {
        result = result.replace(new RegExp(`\\{${paramKey}\\}`, 'g'), String(paramVal));
      }
    }

    return result;
  };
};

const defaultTranslate = createTranslate('en');

const defaultContextValue: I18nContextType = {
  locale: 'en',
  setLocale: () => {},
  t: defaultTranslate,
  dir: 'ltr',
  isRtl: false,
};

export const I18nContext = createContext<I18nContextType>(defaultContextValue);

export const I18nProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [locale, setLocaleState] = useState<Locale>(() => {
    try {
      const saved = localStorage.getItem(LOCALE_STORAGE_KEY);
      if (saved === 'en' || saved === 'he') {
        return saved;
      }
    } catch {
      // ignore
    }
    return 'en'; // Default language MUST be 'en' (English)
  });

  const setLocale = useCallback((newLocale: Locale) => {
    setLocaleState(newLocale);
    try {
      localStorage.setItem(LOCALE_STORAGE_KEY, newLocale);
      document.documentElement.lang = newLocale;
      document.documentElement.dir = newLocale === 'he' ? 'rtl' : 'ltr';
    } catch {
      // ignore
    }
  }, []);

  useEffect(() => {
    document.documentElement.lang = locale;
    document.documentElement.dir = locale === 'he' ? 'rtl' : 'ltr';
  }, [locale]);

  const dir: 'ltr' | 'rtl' = locale === 'he' ? 'rtl' : 'ltr';
  const isRtl = locale === 'he';

  const t = useMemo(() => createTranslate(locale), [locale]);

  const contextValue = useMemo<I18nContextType>(
    () => ({
      locale,
      setLocale,
      t,
      dir,
      isRtl,
    }),
    [locale, setLocale, t, dir, isRtl]
  );

  return <I18nContext.Provider value={contextValue}>{children}</I18nContext.Provider>;
};

export const useTranslation = (): I18nContextType => {
  const context = useContext(I18nContext);
  return context || defaultContextValue;
};

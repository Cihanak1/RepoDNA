import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import en from './locales/en.json';
import tr from './locales/tr.json';

export type SupportedLocale = 'en' | 'tr';

export const getInitialLocale = (): SupportedLocale => {
  try {
    const stored = localStorage.getItem('repodna.locale');
    if (stored) {
      const parsed = JSON.parse(stored);
      if (parsed === 'en' || parsed === 'tr') return parsed;
    }
  } catch {
    // ignore
  }
  if (typeof navigator !== 'undefined' && navigator.language?.toLowerCase().startsWith('tr')) {
    return 'tr';
  }
  return 'en';
};

const initialLocale = getInitialLocale();

void i18n
  .use(initReactI18next)
  .init({
    resources: {
      en: { translation: en },
      tr: { translation: tr },
    },
    lng: initialLocale,
    fallbackLng: 'en',
    interpolation: {
      escapeValue: false,
    },
  });

if (typeof document !== 'undefined') {
  document.documentElement.lang = initialLocale;
}

export default i18n;

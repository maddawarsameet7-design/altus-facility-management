import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import enTranslations from '../locales/en.json';
import hiTranslations from '../locales/hi.json';
import { SecureStorage } from '../services/secureStorage.js';

const translations = {
  hi: hiTranslations,
  en: enTranslations,
};

const I18nContext = createContext({
  locale: 'hi',
  setLocale: () => {},
  t: (key) => key,
  getFriendlyError: () => '',
});

export const I18nProvider = ({ children }) => {
  const [locale, setLocaleState] = useState('hi'); // Default Hindi (Amendment 6)

  useEffect(() => {
    SecureStorage.get('user_locale').then((saved) => {
      if (saved && (saved === 'hi' || saved === 'en')) {
        setLocaleState(saved);
      }
    });
  }, []);

  const setLocale = useCallback(async (newLocale) => {
    if (newLocale === 'hi' || newLocale === 'en') {
      setLocaleState(newLocale);
      await SecureStorage.set('user_locale', newLocale);
    }
  }, []);

  const t = useCallback(
    (key, params = {}) => {
      const currentCatalog = translations[locale] || translations.hi;
      let text = currentCatalog[key] || translations.en[key] || key;

      Object.entries(params).forEach(([k, v]) => {
        text = text.replace(new RegExp(`\\{${k}\\}`, 'g'), String(v));
      });

      return text;
    },
    [locale]
  );

  const getFriendlyError = useCallback(
    (err) => {
      if (!err) return '';
      const msg = typeof err === 'string' ? err : err.message || '';
      const lower = msg.toLowerCase();

      if (err.isNetworkError || lower.includes('failed to fetch') || lower.includes('network request failed')) {
        return t('error_network_offline');
      }

      if (lower.includes('too many') || lower.includes('wait') || lower.includes('429')) {
        const match = msg.match(/(\d+)\s*seconds/i);
        const sec = match ? match[1] : '30';
        return t('error_rate_limited', { seconds: sec });
      }

      if (lower.includes('outside the site geofence') || lower.includes('geofence')) {
        const match = msg.match(/(\d+(\.\d+)?)\s*m/i);
        const dist = match ? match[1] : '50';
        return t('error_geofence_outside', { distance_m: dist });
      }

      if (lower.includes('accuracy too low') || lower.includes('gps')) {
        const match = msg.match(/(\d+(\.\d+)?)\s*m/i);
        const acc = match ? match[1] : '50';
        return t('error_gps_low_accuracy', { accuracy: acc });
      }

      if (lower.includes('reassigned') || lower.includes('covered') || lower.includes('conflict')) {
        return `${t('error_slot_covered')} ${t('error_contact_supervisor')}`;
      }

      return `${msg} - ${t('error_contact_supervisor')}`;
    },
    [t]
  );

  return (
    <I18nContext.Provider value={{ locale, setLocale, t, getFriendlyError }}>
      {children}
    </I18nContext.Provider>
  );
};

export const useI18n = () => useContext(I18nContext);

export default I18nContext;

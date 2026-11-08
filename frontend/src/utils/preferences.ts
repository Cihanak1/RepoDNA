export type WorkstationMode = 'simple' | 'advanced';
export type SupportedLocale = 'en' | 'tr';

function getStorage(): Storage | null {
  try {
    if (typeof window !== 'undefined' && window.localStorage) {
      return window.localStorage;
    }
  } catch {
    /* Storage unavailable */
  }
  return null;
}

export function readPreference<T>(key: string, fallback: T, validate: (value: unknown) => value is T): T {
  try {
    const storage = getStorage();
    if (!storage) return fallback;
    const raw = storage.getItem(`repodna.${key}`);
    if (raw === null) return fallback;
    const value: unknown = JSON.parse(raw);
    return validate(value) ? value : fallback;
  } catch {
    return fallback;
  }
}

export function savePreference(key: string, value: unknown) {
  try {
    const storage = getStorage();
    if (!storage) return;
    storage.setItem(`repodna.${key}`, JSON.stringify(value));
  } catch {
    /* Storage is optional in restricted contexts */
  }
}

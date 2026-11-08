export function readPreference<T>(key: string, fallback: T, validate: (value: unknown) => value is T): T {
  try {
    const value: unknown = JSON.parse(localStorage.getItem(`repodna.${key}`) ?? 'null');
    return validate(value) ? value : fallback;
  } catch { return fallback; }
}

export function savePreference(key: string, value: unknown) {
  try { localStorage.setItem(`repodna.${key}`, JSON.stringify(value)); } catch { /* Storage is optional. */ }
}

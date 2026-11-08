import { describe, expect, it } from 'vitest';
import en from '../locales/en.json';
import tr from '../locales/tr.json';
import i18n from '../i18n';
import { readPreference, savePreference } from '../utils/preferences';
import { normalizeSearchText } from '../utils/graphLayout';

function getLeafKeys(obj: Record<string, unknown>, prefix = ''): string[] {
  let keys: string[] = [];
  for (const [key, value] of Object.entries(obj)) {
    const fullPath = prefix ? `${prefix}.${key}` : key;
    if (value && typeof value === 'object' && !Array.isArray(value)) {
      keys = keys.concat(getLeafKeys(value as Record<string, unknown>, fullPath));
    } else {
      keys.push(fullPath);
    }
  }
  return keys.sort();
}

describe('i18n and Localization Integrity', () => {
  it('guarantees exact parity between English and Turkish translation keys', () => {
    const enKeys = getLeafKeys(en as Record<string, unknown>);
    const trKeys = getLeafKeys(tr as Record<string, unknown>);

    const missingInTr = enKeys.filter((k) => !trKeys.includes(k));
    const missingInEn = trKeys.filter((k) => !enKeys.includes(k));

    expect(missingInTr).toEqual([]);
    expect(missingInEn).toEqual([]);
    expect(enKeys.length).toBe(trKeys.length);
    expect(enKeys.length).toBeGreaterThan(60);
  });

  it('switches languages dynamically without reload', async () => {
    await i18n.changeLanguage('tr');
    expect(i18n.language).toBe('tr');
    expect(i18n.t('launchpad.headline')).toBe(
      'Projendeki dosyaların ve modüllerin nasıl birbirine bağlandığını keşfet.'
    );

    await i18n.changeLanguage('en');
    expect(i18n.language).toBe('en');
    expect(i18n.t('launchpad.headline')).toBe(
      "Understand how your project's files and modules connect."
    );
  });

  it('properly handles Turkish case folding (İ/ı) for search comparison', () => {
    const samplePaths = [
      'src/İletişim/servis.ts',
      'src/islem/Hesapla.ts',
      'src/Infrastructure/Window.cs',
    ];

    const searchTurkish = (query: string) => {
      const q = normalizeSearchText(query);
      return samplePaths.filter((p) => normalizeSearchText(p).includes(q));
    };

    // 'i' matches 'İletişim' and 'İLETİŞİM'
    expect(searchTurkish('iletişim')).toContain('src/İletişim/servis.ts');
    expect(searchTurkish('İLETİŞİM')).toContain('src/İletişim/servis.ts');
    expect(searchTurkish('iletisim')).toContain('src/İletişim/servis.ts');

    // 'islem' matches 'Hesapla' if containing islem, and 'infrastructure'
    expect(searchTurkish('islem')).toContain('src/islem/Hesapla.ts');
    expect(searchTurkish('infrastructure')).toContain('src/Infrastructure/Window.cs');
    expect(searchTurkish('Infrastructure')).toContain('src/Infrastructure/Window.cs');
    expect(searchTurkish('ınfrastructure')).toContain('src/Infrastructure/Window.cs');
  });

  it('persists and validates workstation mode preferences correctly', () => {
    savePreference('mode', 'advanced');
    const mode = readPreference<'simple' | 'advanced'>(
      'mode',
      'simple',
      (v): v is 'simple' | 'advanced' => v === 'simple' || v === 'advanced'
    );
    expect(mode).toBe('advanced');

    // Invalid fallback
    savePreference('mode', 'ultra-pro');
    const fallbackMode = readPreference<'simple' | 'advanced'>(
      'mode',
      'simple',
      (v): v is 'simple' | 'advanced' => v === 'simple' || v === 'advanced'
    );
    expect(fallbackMode).toBe('simple');
  });
});

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

  it('verifies deterministic ARCH-001..ARCH-006 and SEC-001 health rules parity in both locales', () => {
    const requiredRules = [
      'ARCH-001',
      'ARCH-002',
      'ARCH-003',
      'ARCH-004',
      'ARCH-005',
      'ARCH-006',
      'SEC-001',
    ] as const;

    for (const ruleId of requiredRules) {
      const enRule = en.rules[ruleId];
      const trRule = tr.rules[ruleId];

      expect(enRule, `EN missing rule ${ruleId}`).toBeDefined();
      expect(trRule, `TR missing rule ${ruleId}`).toBeDefined();
      expect(enRule.title.length).toBeGreaterThan(5);
      expect(trRule.title.length).toBeGreaterThan(5);
      expect(enRule.remediation.length).toBeGreaterThan(15);
      expect(trRule.remediation.length).toBeGreaterThan(15);
    }
  });

  it('verifies backend error codes are mapped in both locales', () => {
    const requiredErrors = [
      'SCAN_CANCELLED',
      'SCAN_TIMEOUT',
      'INTERNAL_SCAN_ERROR',
      'JOB_NOT_FOUND',
      'ANALYSIS_NOT_FOUND',
      'RESULT_NOT_READY',
      'EMPTY_URL',
      'INVALID_URL_CHARS',
      'SSRF_IP_LITERAL',
      'SSRF_LOCAL_HOST',
      'EMPTY_PATH',
      'PATH_NOT_FOUND',
      'NOT_A_DIRECTORY',
      'SYSTEM_DIR_BLOCKED',
      'FILESYSTEM_ROOT_BLOCKED',
      'SCAN_FAILED',
    ] as const;

    for (const errCode of requiredErrors) {
      expect(en.errors[errCode], `EN missing error ${errCode}`).toBeDefined();
      expect(tr.errors[errCode], `TR missing error ${errCode}`).toBeDefined();
    }
  });

  it('verifies confidence explanation reflects coverage-based proxy rather than empirical probability', () => {
    expect(en.help.confidenceDesc).toContain('coverage-based');
    expect(en.help.confidenceDesc).not.toContain('accuracy percentage');
    expect(tr.help.confidenceDesc).toContain('kapsam temelli');
  });
});

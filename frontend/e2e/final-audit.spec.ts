import { expect, test } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

const ARTIFACTS = '../docs/design/after';

test.describe('RepoDNA v0.2.0 Final Release Readiness & Visual Proof Audit', () => {
  test('generates all 8 required visual proof screenshots across 1440x900 and 390x844', async ({ page }) => {
    test.setTimeout(90000);

    // 1. Desktop resolution: 1440x900
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto('/');
    await expect(page.getByTestId('welcome-launchpad')).toBeVisible();

    // Switch to Turkish
    await page.getByTestId('lang-tr-btn').click();
    expect(await page.evaluate(() => document.documentElement.lang)).toBe('tr');

    // Launch Demo Dataset
    await page.getByTestId('launchpad-demo-btn').click();
    await expect(page.getByTestId('summary-health-score')).toBeVisible();

    // Ensure Simple Mode is active
    await page.getByTestId('mode-simple-btn').click();
    await expect(page.getByTestId('mode-simple-btn')).toHaveAttribute('aria-pressed', 'true');

    // Verify 1440x900 horizontal scroll
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);

    // Screenshot 1: Türkçe Basit Mod — RepoDNA
    await page.screenshot({ path: `${ARTIFACTS}/1-tr-simple-repodna.png` });

    // Switch to English in Simple Mode
    await page.getByTestId('lang-en-btn').click();
    expect(await page.evaluate(() => document.documentElement.lang)).toBe('en');
    await expect(page.getByRole('button', { name: 'Architecture Studio' })).toBeVisible();

    // Screenshot 2: İngilizce Basit Mod — RepoDNA
    await page.screenshot({ path: `${ARTIFACTS}/2-en-simple-repodna.png` });

    // Switch to Turkish, then switch to Advanced Mode
    await page.getByTestId('lang-tr-btn').click();
    await page.getByTestId('mode-advanced-btn').click();
    await expect(page.getByTestId('mode-advanced-btn')).toHaveAttribute('aria-pressed', 'true');
    await expect(page.getByTestId('summary-ast-coverage')).toBeVisible();

    // Screenshot 3: Türkçe Gelişmiş Mod
    await page.screenshot({ path: `${ARTIFACTS}/3-tr-advanced-repodna.png` });

    // Group graph by package clusters
    const collapsePkgBtn = page.getByRole('button', { name: /Paketleri Kümele|Collapse Packages/i });
    if (await collapsePkgBtn.isVisible()) {
      await collapsePkgBtn.click();
      await page.waitForTimeout(300);
    }

    // Screenshot 8: Büyük graf — paket görünümü
    await page.screenshot({ path: `${ARTIFACTS}/8-package-clusters-graph.png` });

    // Open Guided Onboarding Tour
    await page.getByTestId('open-tour-btn').click();
    const tourModal = page.getByTestId('onboarding-tour-modal');
    await expect(tourModal).toBeVisible();

    // Screenshot 7: İlk kullanım rehberi
    await page.screenshot({ path: `${ARTIFACTS}/7-onboarding-guide.png` });
    await page.keyboard.press('Escape');
    await expect(tourModal).toBeHidden();

    // Switch to English and open Health & Transparency Report
    await page.getByTestId('lang-en-btn').click();
    await page.getByRole('button', { name: /Health & Transparency Report/i }).click();
    await expect(page.getByTestId('health-report-view')).toBeVisible();

    // Screenshot 5: İngilizce Health Report
    await page.screenshot({ path: `${ARTIFACTS}/5-en-health-report.png` });

    // Switch to Turkish while on Health Report to check NiceWP honest low coverage reporting
    await page.getByTestId('lang-tr-btn').click();
    await expect(page.getByText('Önemli Bulgular ve Çözüm Planı')).toBeVisible();

    // Analyze live NiceWP repository via GitHub HTTPS
    const changeRepoBtn = page.getByRole('button', { name: /Depo değiştir|Change repository/i });
    if (await changeRepoBtn.isVisible()) await changeRepoBtn.click();
    await page.getByRole('button', { name: /GitHub HTTPS/i }).click();
    const repoInput = page.locator('#repo-target-input');
    await repoInput.fill('https://github.com/Cihanak1/NiceWP');
    await page.getByTestId('analyze-submit-btn').click();

    // Wait for scan to complete
    await expect(page.getByTestId('previous-analysis-banner')).toBeHidden({ timeout: 60000 });
    await expect(page.getByTestId('dependency-graph-canvas')).toBeVisible();

    // Switch to Health Report in Turkish to inspect honest low coverage notice
    await page.getByRole('button', { name: /Sağlık ve Şeffaflık Raporu/i }).click();
    await expect(page.getByTestId('health-report-view')).toBeVisible();
    await expect(page.getByTestId('report-overall-score-status')).toContainText(
      /Değerlendirilmedi|Not Evaluated/i
    );
    await expect(page.getByTestId('unverified-rules-box')).toBeVisible();

    // Screenshot 4: Türkçe NiceWP düşük kapsam raporu
    await page.screenshot({ path: `${ARTIFACTS}/4-tr-nicewp-low-coverage-report.png` });

    // 2. Mobile resolution: 390x844
    await page.setViewportSize({ width: 390, height: 844 });
    await page.getByRole('button', { name: /Mimari İnceleme|Architecture Studio/i }).click();
    await expect(page.getByTestId('dependency-graph-canvas')).toBeVisible();

    // Verify 390x844 horizontal scroll integrity
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);

    // Screenshot 6: Mobil Türkçe görünüm
    await page.screenshot({ path: `${ARTIFACTS}/6-tr-mobile-workstation.png` });

    // 3. Automated Axe Accessibility Audit across mobile view
    const a11y = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa', 'wcag21aa', 'wcag22aa'])
      .analyze();
    expect(a11y.violations).toEqual([]);
  });

  test('preserves selected module, active tab, and panel states during dynamic language switching', async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto('/');
    await page.getByTestId('launchpad-demo-btn').click();
    await expect(page.getByTestId('summary-health-score')).toBeVisible();

    // Select a file from Explorer
    await page.getByTestId('explorer-file-src/api/router.py').click();
    const inspector = page.getByTestId('inspector-panel');
    await expect(inspector).toBeVisible();
    await expect(page.getByTestId('inspector-file-title')).toHaveText('src/api/router.py');

    // Switch to Turkish
    await page.getByTestId('lang-tr-btn').click();
    expect(await page.evaluate(() => document.documentElement.lang)).toBe('tr');

    // Verify selected module remains EXACTLY the same and inspector is open
    await expect(inspector).toBeVisible();
    await expect(page.getByTestId('inspector-file-title')).toHaveText('src/api/router.py');
    await expect(inspector).toHaveAttribute('aria-label', 'Seçili Modül Denetçisi');
    await expect(page.getByRole('button', { name: 'Yolu kopyala' })).toBeVisible();

    // Switch back to English
    await page.getByTestId('lang-en-btn').click();
    expect(await page.evaluate(() => document.documentElement.lang)).toBe('en');

    // Verify selection and panel still preserved
    await expect(inspector).toBeVisible();
    await expect(page.getByTestId('inspector-file-title')).toHaveText('src/api/router.py');
    await expect(inspector).toHaveAttribute('aria-label', 'Selected Module Inspector');
    await expect(page.getByRole('button', { name: 'Copy path' })).toBeVisible();
  });
});

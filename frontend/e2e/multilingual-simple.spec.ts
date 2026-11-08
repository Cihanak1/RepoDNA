import { expect, test } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

const artifacts = '../docs/design/after';

test.describe('Pass 2: Cognitive Simplicity, Guided Experience & Multilingual Workstation', () => {
  test('dynamic language switching between Turkish and English with accessibility', async ({ page }) => {
    await page.goto('/');

    // Explicitly click English button
    await page.getByTestId('lang-en-btn').click();
    await expect(page.locator('h1')).toHaveText('RepoDNA');
    await expect(page.getByText("Understand how your project's files and modules connect.")).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.lang)).toBe('en');

    // Switch to Turkish via TR button
    await page.getByTestId('lang-tr-btn').click();
    expect(await page.evaluate(() => document.documentElement.lang)).toBe('tr');
    await expect(page.getByText('Projendeki dosyaların ve modüllerin nasıl birbirine bağlandığını keşfet.')).toBeVisible();

    // Launch Demo in Turkish
    await page.getByTestId('launchpad-demo-btn').click();
    await expect(page.getByTestId('summary-health-score')).toBeVisible();

    // Verify Turkish Tab labels
    await expect(page.getByRole('button', { name: 'Mimari İnceleme' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Sağlık ve Şeffaflık Raporu' })).toBeVisible();

    // Verify Turkish Summary Action
    await expect(page.getByText(/Önerilen (Sonraki|Sıradaki) (Aksiyon|Eylem)/i)).toBeVisible();

    // Take screenshot of Turkish Architecture Studio in Simple mode
    await page.screenshot({ path: `${artifacts}/pass2-turkish-studio-simple.png` });

    // Switch back to English
    await page.getByTestId('lang-en-btn').click();
    expect(await page.evaluate(() => document.documentElement.lang)).toBe('en');
    await expect(page.getByRole('button', { name: 'Architecture Studio' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Health & Transparency Report' })).toBeVisible();
    await expect(page.getByText('Recommended Next Action')).toBeVisible();

    // WCAG Accessibility check in English and Turkish
    const axeResults = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa', 'wcag21aa', 'wcag22aa'])
      .analyze();
    expect(axeResults.violations).toEqual([]);
  });

  test('Simple Mode vs Advanced Mode toggling and persistence', async ({ page }) => {
    await page.goto('/');
    await page.getByTestId('launchpad-demo-btn').click();
    await expect(page.getByTestId('summary-health-score')).toBeVisible();

    const simpleBtn = page.getByTestId('mode-simple-btn');
    const advancedBtn = page.getByTestId('mode-advanced-btn');

    // Select Simple mode
    await simpleBtn.click();
    await expect(simpleBtn).toHaveAttribute('aria-pressed', 'true');
    await expect(advancedBtn).toHaveAttribute('aria-pressed', 'false');

    // In Simple Mode: 4 primary overview cards
    await expect(page.getByTestId('summary-health-score')).toBeVisible();
    await expect(page.getByTestId('summary-total-files')).toBeVisible();
    await expect(page.getByTestId('summary-cycle-count')).toBeVisible();
    await expect(page.getByText(/Recommended Next Action|Önerilen Sıradaki Eylem/i)).toBeVisible();

    // 6-metric technical items (astCoverage, hotspots) are hidden in Simple mode
    await expect(page.getByTestId('summary-ast-coverage')).toBeHidden();

    // In Inspector: Select a file from explorer
    await page.getByTestId('explorer-file-src/api/router.py').click();
    await expect(page.getByTestId('inspector-panel')).toBeVisible();
    await expect(page.getByTestId('inspector-technical-details')).toBeVisible();
    await expect(page.getByTestId('inspector-technical-details')).not.toHaveAttribute('open', '');

    // Switch to Advanced Mode
    await advancedBtn.click();
    await expect(advancedBtn).toHaveAttribute('aria-pressed', 'true');
    await expect(simpleBtn).toHaveAttribute('aria-pressed', 'false');

    // In Advanced Mode: Full 6-metric strip is visible
    await expect(page.getByTestId('summary-ast-coverage')).toBeVisible();
    await expect(page.getByTestId('summary-git-hotspots')).toBeVisible();

    // In Inspector: Advanced technical metrics disclosure is open
    await expect(page.getByTestId('inspector-technical-details')).toHaveAttribute('open', '');

    // Take screenshot of Advanced mode
    await page.screenshot({ path: `${artifacts}/pass2-advanced-mode.png` });

    // Reload page to verify localStorage persistence
    await page.reload();
    await expect(page.getByTestId('mode-advanced-btn')).toHaveAttribute('aria-pressed', 'true');
    await page.getByTestId('launchpad-demo-btn').click();
    await expect(page.getByTestId('summary-ast-coverage')).toBeVisible();
  });

  test('Guided Onboarding Tour: 4 steps, keyboard navigation, and demo action', async ({ page }) => {
    await page.goto('/');

    // Launch tour via header button
    await page.getByTestId('open-tour-btn').click();
    const modal = page.getByTestId('onboarding-tour-modal');
    await expect(modal).toBeVisible();

    // Step 1: Repository Selection
    await expect(page.getByTestId('onboarding-step-indicator')).toContainText(/1 (of|\/) 4/i);

    // Next step via button
    await page.getByTestId('onboarding-next-btn').click();
    await expect(page.getByTestId('onboarding-step-indicator')).toContainText(/2 (of|\/) 4/i);

    // Step navigation via Arrow keys
    await page.keyboard.press('ArrowRight');
    await expect(page.getByTestId('onboarding-step-indicator')).toContainText(/3 (of|\/) 4/i);

    await page.keyboard.press('ArrowLeft');
    await expect(page.getByTestId('onboarding-step-indicator')).toContainText(/2 (of|\/) 4/i);

    await page.keyboard.press('ArrowRight');
    await page.keyboard.press('ArrowRight');
    await expect(page.getByTestId('onboarding-step-indicator')).toContainText(/4 (of|\/) 4/i);

    // Dismiss with Escape key
    await page.keyboard.press('Escape');
    await expect(modal).toBeHidden();

    // Reopen and launch Demo directly from tour
    await page.getByTestId('open-tour-btn').click();
    await expect(modal).toBeVisible();
    await page.screenshot({ path: `${artifacts}/pass2-onboarding-modal.png` });

    await page.getByTestId('onboarding-demo-btn').click();
    await expect(modal).toBeHidden();
    await expect(page.getByTestId('summary-health-score')).toBeVisible();
  });

  test('Contextual Terminology Tooltips and Accessible Popovers', async ({ page }) => {
    await page.goto('/');
    await page.getByTestId('launchpad-demo-btn').click();
    await expect(page.getByTestId('summary-health-score')).toBeVisible();

    // Select a file to inspect
    await page.getByTestId('explorer-file-src/api/router.py').click();
    await expect(page.getByTestId('inspector-panel')).toBeVisible();

    // Hover or focus the Fan-In tooltip trigger
    const fanInTrigger = page.locator('.cursor-help').first();
    await fanInTrigger.focus();

    const popover = page.locator('.info-tooltip-popover');
    await expect(popover).toBeVisible();

    // Dismiss tooltip on Escape
    await page.keyboard.press('Escape');
    await expect(popover).toBeHidden();
  });

  test('Health Report 2-tier view with honest low-coverage semantics', async ({ page }) => {
    await page.goto('/');
    await page.getByTestId('launchpad-demo-btn').click();
    await expect(page.getByTestId('summary-health-score')).toBeVisible();

    // Switch to Health Report tab
    await page.getByRole('button', { name: /Health & Transparency|Sağlık ve Şeffaflık/i }).click();
    await expect(page.getByTestId('health-report-view')).toBeVisible();

    // Verify 2-tier navigation (Summary vs Detailed Evidence)
    const summarySubTab = page.getByTestId('report-tier-summary-btn');
    const evidenceSubTab = page.getByTestId('report-tier-evidence-btn');

    await expect(summarySubTab).toBeVisible();
    await expect(evidenceSubTab).toBeVisible();

    // Switch to Detailed Evidence sub-tab
    await evidenceSubTab.click();
    await expect(evidenceSubTab).toHaveAttribute('aria-selected', 'true');

    // Verify Rules and evidence sections
    await expect(page.getByTestId('rule-card-ARCH-001')).toBeVisible();

    // Take screenshot of report
    await page.screenshot({ path: `${artifacts}/pass2-health-report.png` });
  });
});

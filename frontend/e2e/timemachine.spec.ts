import { expect, test } from '@playwright/test';

const ARTIFACT_DIR = '../docs/design/after';

test.describe('RepoDNA v0.6.0 — Architecture Time Machine E2E Audit', () => {
  test.setTimeout(180000);

  test('verifies commit history, time scrubber, snapshot details, evolution diff, evidence blob inspector, trends, localization and themes', async ({
    page,
  }) => {
    // 1. Visit App
    await page.goto('/');
    await expect(page.getByTestId('welcome-launchpad')).toBeVisible();

    // Ensure English initially
    const enBtn = page.getByTestId('lang-en-btn');
    if (await enBtn.isVisible()) {
      await enBtn.click();
    }

    // 2. Run real live scan on workspace
    const scanBtn = page.getByTestId('launchpad-scan-workspace-btn');
    await expect(scanBtn).toBeVisible();
    await scanBtn.click();

    // Wait for scan completion
    await expect(page.getByTestId('summary-health-score')).toBeVisible({ timeout: 35000 });
    await expect(page.getByTestId('tab-history-btn')).toBeVisible();

    // 3. Navigate to Time Machine Tab
    await page.getByTestId('tab-history-btn').click();
    await expect(page.getByTestId('time-machine-workstation')).toBeVisible();

    // Verify sub-tabs exist
    await expect(page.getByTestId('tm-subtab-timeline-btn')).toBeVisible();
    await expect(page.getByTestId('tm-subtab-diff-btn')).toBeVisible();
    await expect(page.getByTestId('tm-subtab-trends-btn')).toBeVisible();

    // 4. Verify commit history list in Timeline view
    await expect(page.getByTestId('commit-list-container')).toBeVisible({ timeout: 15000 });
    const commitItems = page.locator('[data-testid^="commit-item-"]');
    await expect(commitItems.first()).toBeVisible({ timeout: 10000 });

    // Filter commits via search
    await page.getByTestId('commit-search-input').fill('feat');
    await page.waitForTimeout(300);
    await page.getByTestId('commit-search-input').clear();
    await page.waitForTimeout(200);

    // Select the first commit to inspect snapshot
    await commitItems.first().click();
    await expect(page.getByText(/Module Inventory & Evidence/i)).toBeVisible({ timeout: 15000 });

    // Screenshot 1: Time Machine Timeline & Snapshot
    await page.screenshot({ path: `${ARTIFACT_DIR}/timemachine-1-timeline-snapshot.png` });

    // 5. Open Historical Evidence Blob Inspector Modal
    const moduleItems = page.locator('[data-testid^="snapshot-module-"]');
    await expect(moduleItems.first()).toBeVisible({ timeout: 15000 });
    await moduleItems.first().click();
    await expect(page.getByTestId('evidence-inspector-modal')).toBeVisible({ timeout: 10000 });
    await expect(page.getByText('Historical Git Blob Evidence Inspector')).toBeVisible();
    await expect(page.getByText(/Cryptographically Verified Historical Blob/i)).toBeVisible();

    // Screenshot 2: Historical Git Blob Modal
    await page.screenshot({ path: `${ARTIFACT_DIR}/timemachine-2-evidence-modal.png` });

    // Close modal
    const closeBtn = page.getByRole('button').filter({ has: page.locator('svg.lucide-x') }).first();
    await expect(closeBtn).toBeVisible();
    await closeBtn.click();
    await expect(page.getByTestId('evidence-inspector-modal')).not.toBeVisible();

    // 6. Navigate to Evolution Diff Subtab
    await page.getByTestId('tm-subtab-diff-btn').click();
    await expect(page.getByTestId('diff-base-select')).toBeVisible();
    await expect(page.getByTestId('diff-head-select')).toBeVisible();

    // Select base and head commits
    const baseOptions = page.locator('[data-testid="diff-base-select"] option');
    const headOptions = page.locator('[data-testid="diff-head-select"] option');
    await expect(baseOptions.first()).toBeAttached();
    const optCount = await baseOptions.count();
    expect(optCount).toBeGreaterThanOrEqual(2);

    const baseVal = await baseOptions.nth(optCount - 1).getAttribute('value');
    const headVal = await headOptions.nth(0).getAttribute('value');
    expect(baseVal).toBeTruthy();
    expect(headVal).toBeTruthy();
    await page.getByTestId('diff-base-select').selectOption(baseVal!);
    await page.getByTestId('diff-head-select').selectOption(headVal!);

    // Run comparison
    await page.getByTestId('run-diff-btn').click();
    await expect(page.getByTestId('evolution-diff-content')).toBeVisible({ timeout: 20000 });

    // Screenshot 3: Evolution Diff
    await page.screenshot({ path: `${ARTIFACT_DIR}/timemachine-3-evolution-diff.png` });

    // 7. Navigate to Architecture Trends Subtab
    await page.getByTestId('tm-subtab-trends-btn').click();
    await expect(page.getByText('Historical Architectural Progression')).toBeVisible();
    await expect(page.locator('table')).toBeVisible({ timeout: 90000 });

    // Screenshot 4: Architecture Trends
    await page.screenshot({ path: `${ARTIFACT_DIR}/timemachine-4-trends.png` });

    // 8. Internationalization (Turkish switch)
    const trBtn = page.getByTestId('lang-tr-btn');
    await expect(trBtn).toBeVisible();
    await trBtn.click();
    await page.waitForTimeout(300);
    await expect(page.getByText(/Zaman Tüneli|Evrimsel Fark|Mimari Trendleri/i).first()).toBeVisible();

    // Screenshot 5: Turkish Localization
    await page.screenshot({ path: `${ARTIFACT_DIR}/timemachine-5-turkish.png` });

    // Switch back to English
    const enBtnAfter = page.getByTestId('lang-en-btn');
    await expect(enBtnAfter).toBeVisible();
    await enBtnAfter.click();

    // 9. Theme toggle (Light theme)
    const themeToggleBtn = page.getByTestId('theme-toggle-btn');
    await expect(themeToggleBtn).toBeVisible();
    await themeToggleBtn.click();
    await page.waitForTimeout(300);

    // Screenshot 6: Light Theme
    await page.screenshot({ path: `${ARTIFACT_DIR}/timemachine-6-light-theme.png` });

    // Toggle back to dark
    await themeToggleBtn.click();
  });
});

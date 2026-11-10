import { expect, test } from '@playwright/test';

const ARTIFACT_DIR = '../docs/design/after';

test.describe('RepoDNA v0.5.0 — Intelligence Workstation, Passport v2 & Production E2E Audit', () => {
  test.setTimeout(120000);

  test('verifies live scan, smart search, symbol trace, evidence inspector, context generator presets, passport v1/v2, localization, viewports, and themes', async ({
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

    // 2. Run real live workspace scan on RepoDNA
    const scanBtn = page.getByTestId('launchpad-scan-workspace-btn');
    await expect(scanBtn).toBeVisible();
    await scanBtn.click();

    // Wait for real scan completion
    await expect(page.getByTestId('summary-health-score')).toBeVisible({ timeout: 25000 });
    await expect(page.getByTestId('tab-intelligence-btn')).toBeVisible();

    // 3. Navigate to Intelligence Workstation Tab
    await page.getByTestId('tab-intelligence-btn').click();
    await expect(page.getByTestId('subtab-search-btn')).toBeVisible();

    // 4. Test Smart Code Explorer Search
    await expect(page.getByTestId('smart-search-input')).toBeVisible();
    await page.getByTestId('smart-search-input').fill('analyzer');
    await page.getByTestId('smart-search-submit-btn').click();

    // Verify search results populate with scoring & rationale
    await expect(page.getByText(/Found \d+ matching modules?/i)).toBeVisible({ timeout: 30000 });
    await expect(page.getByText(/Scoring & Retrieval Rationale/i).first()).toBeVisible();

    // 5. Click Matched Symbol to trigger Symbol Relationship Trace
    const traceBtn = page.getByTestId('trace-symbol-btn').first();
    if (await traceBtn.isVisible()) {
      await traceBtn.click();
      // Verifies auto-switch to symbol relations subtab
      await expect(page.getByText(/Definition/i).first()).toBeVisible({ timeout: 10000 });
      await expect(page.getByText(/Callers|Callees|Container Hierarchy|Blast Radius/i).first()).toBeVisible();
    }

    // 6. Navigate to Evidence Ledger Subtab
    await page.getByTestId('subtab-evidence-btn').click();
    await expect(page.getByText(/Architectural Evidence Ledger/i)).toBeVisible();
    await expect(page.getByTestId('verify-staleness-btn')).toBeVisible();

    // Click verify staleness
    await page.getByTestId('verify-staleness-btn').click();
    await page.waitForTimeout(500);

    // Select an evidence item to inspect details
    const firstEvItem = page.getByTestId('evidence-item-btn').first();
    if (await firstEvItem.isVisible()) {
      await firstEvItem.click();
      await expect(page.getByText(/Git Revision:/i)).toBeVisible();
      await expect(page.getByText(/Code Snippet/i)).toBeVisible();
    }

    // 7. Navigate to Agent Context Subtab & Test Presets (500, 2000, minimal contract)
    await page.getByTestId('subtab-context-btn').click();
    await expect(page.getByText(/AI Agent Architecture Context Generator/i)).toBeVisible();

    // Test Preset 500
    await page.getByTestId('preset-500-btn').click();
    await page.getByTestId('generate-context-btn').click();
    await expect(page.getByText(/Context Size/i)).toBeVisible({ timeout: 10000 });
    await expect(page.getByText(/BUDGET COMPLIANT|TRUNCATED TO FIT BUDGET/i)).toBeVisible();

    // Test Preset 2000
    await page.getByTestId('preset-2000-btn').click();
    await page.getByTestId('generate-context-btn').click();
    await expect(page.getByText(/Context Size/i)).toBeVisible({ timeout: 10000 });

    // Test Minimal Contract
    await page.getByTestId('minimal-contract-checkbox').check();
    await page.getByTestId('generate-context-btn').click();
    await expect(page.getByText(/Context Size/i)).toBeVisible({ timeout: 10000 });
    await page.getByTestId('minimal-contract-checkbox').uncheck();

    // 8. Test Repository Passport v1 / v2 Toggle & View
    await page.getByTestId('tab-passport-btn').click();
    await expect(page.getByText(/Repository Passport/i)).toBeVisible();
    await expect(page.getByTestId('passport-v2-btn')).toBeVisible();
    await expect(page.getByTestId('passport-v1-btn')).toBeVisible();

    // Switch to v1 (legacy)
    await page.getByTestId('passport-v1-btn').click();
    await page.waitForTimeout(400);

    // Switch back to v2.0 (brain)
    await page.getByTestId('passport-v2-btn').click();
    await page.waitForTimeout(400);
    await expect(page.getByText(/v2.0/i).first()).toBeVisible();

    // 9. Test Localization: Switch to Turkish and back to English
    const trBtn = page.getByTestId('lang-tr-btn');
    if (await trBtn.isVisible()) {
      await trBtn.click();
      expect(await page.evaluate(() => document.documentElement.lang)).toBe('tr');
      await page.waitForTimeout(300);

      // Switch back to English
      await page.getByTestId('lang-en-btn').click();
      expect(await page.evaluate(() => document.documentElement.lang)).toBe('en');
    }

    // 10. Switch back to Intelligence tab for responsive screenshots
    await page.getByTestId('tab-intelligence-btn').click();
    await page.waitForTimeout(300);

    // Capture Desktop Viewport (1366x768)
    await page.setViewportSize({ width: 1366, height: 768 });
    await page.waitForTimeout(250);
    await page.screenshot({ path: `${ARTIFACT_DIR}/intelligence-workstation-1366.png` });

    // Capture Tablet Viewport (1024x768)
    await page.setViewportSize({ width: 1024, height: 768 });
    await page.waitForTimeout(250);
    await page.screenshot({ path: `${ARTIFACT_DIR}/intelligence-workstation-1024.png` });

    // Capture Mobile Viewport (390x844)
    await page.setViewportSize({ width: 390, height: 844 });
    await page.waitForTimeout(250);
    await page.screenshot({ path: `${ARTIFACT_DIR}/intelligence-workstation-390.png` });

    // Reset to standard studio desktop (1440x900) and capture studio view
    await page.setViewportSize({ width: 1440, height: 900 });
    const themeBtn = page.getByTestId('theme-toggle-btn');
    if (await themeBtn.isVisible()) {
      await themeBtn.click();
      await page.waitForTimeout(200);
      await themeBtn.click();
    }
    await page.screenshot({ path: `${ARTIFACT_DIR}/intelligence-workstation-studio.png` });
  });
});

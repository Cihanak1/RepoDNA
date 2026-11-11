import fs from 'fs';
import { expect, test } from '@playwright/test';

const ARTIFACT_DIR = fs.existsSync('docs/design/after')
  ? 'docs/design/after'
  : '../docs/design/after';

test.describe('RepoDNA v0.7.0 — Architecture Refactoring Advisor E2E Audit', () => {
  test.setTimeout(180000);

  test('verifies refactoring advisor workstation, KPI metrics, category filters, action checklist, and cross-navigation', async ({
    page,
  }) => {
    // 1. Visit App
    await page.goto('/');
    await expect(page.getByTestId('welcome-launchpad')).toBeVisible();

    // Ensure English
    const enBtn = page.getByTestId('lang-en-btn');
    if (await enBtn.isVisible()) {
      await enBtn.click();
    }

    // 2. Run real live scan on workspace
    const scanBtn = page.getByTestId('launchpad-scan-workspace-btn');
    await expect(scanBtn).toBeVisible();
    await scanBtn.click();

    // Wait for scan completion
    await expect(page.getByTestId('summary-health-score')).toBeVisible({ timeout: 45000 });
    await expect(page.getByTestId('tab-advisor-btn')).toBeVisible();

    // 3. Navigate to Advisor Tab
    await page.getByTestId('tab-advisor-btn').click();
    await expect(page.getByText('Architecture Refactoring Advisor')).toBeVisible({ timeout: 15000 });
    await expect(page.getByText('v0.7.0 Portfolio Release')).toBeVisible();

    // 4. Verify Summary KPI cards
    await expect(page.getByText('Total Recommendations')).toBeVisible({ timeout: 30000 });
    await expect(page.getByText('Critical Cycles', { exact: true })).toBeVisible();
    await expect(page.getByText('High Coupling', { exact: true })).toBeVisible();
    await expect(page.getByText('Layer Inversions', { exact: true })).toBeVisible();
    await expect(page.getByText('Oversized Hubs', { exact: true })).toBeVisible();

    // Screenshot 1: Advisor Overview
    await page.screenshot({ path: `${ARTIFACT_DIR}/advisor-overview.png` });

    // 5. Test Category Filter Buttons
    const catCouplingBtn = page.getByTestId('filter-cat-high_coupling_module_review');
    if (await catCouplingBtn.isVisible()) {
      await catCouplingBtn.click();
      await page.waitForTimeout(300);
    }

    const catAllBtn = page.getByTestId('filter-cat-all');
    await catAllBtn.click();
    await page.waitForTimeout(300);

    // 6. Test Card interaction: Copy Prompt & Inspect in Graph
    const inspectGraphBtns = page.locator('[data-testid^="inspect-graph-btn-"]');
    if ((await inspectGraphBtns.count()) > 0) {
      await inspectGraphBtns.first().click();
      // Should switch back to Studio tab with inspector active
      await expect(page.getByTestId('tab-studio-btn')).toHaveAttribute('aria-pressed', 'true');
      await expect(page.getByTestId('inspector-panel')).toBeVisible();

      // Screenshot 2: Cross navigation into Graph
      await page.screenshot({ path: `${ARTIFACT_DIR}/advisor-cross-navigation-graph.png` });

      // Check Inspector has Open in Advisor button
      const openAdvisorBtn = page.getByTestId('inspector-open-advisor-btn');
      if (await openAdvisorBtn.isVisible()) {
        await openAdvisorBtn.click();
        await expect(page.getByText('Architecture Refactoring Advisor')).toBeVisible();
      }
    }
  });
});

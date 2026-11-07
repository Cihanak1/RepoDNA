import { expect, test } from '@playwright/test';

test.describe('RepoDNA End-to-End Verification', () => {
  test('loads launchpad, analyzes live local workspace, inspects dependency graph, and views health report', async ({
    page,
  }) => {
    await page.goto('/');

    // 1. Verify no auto-scan occurred; launchpad is visible
    await expect(page.getByTestId('welcome-launchpad')).toBeVisible();
    await expect(page.getByRole('heading', { name: 'RepoDNA', exact: true })).toBeVisible();

    // 2. Click "Analyze Current Workspace" to run a real live scan on RepoDNA itself
    const scanWorkspaceBtn = page.getByTestId('launchpad-scan-workspace-btn');
    await expect(scanWorkspaceBtn).toBeVisible();
    await scanWorkspaceBtn.click();

    // 3. Verify real scan results populate the Summary Strip, Explorer, Graph, and Inspector
    await expect(page.getByTestId('summary-health-score')).toBeVisible({ timeout: 15000 });
    await expect(page.getByTestId('dependency-graph-canvas')).toBeVisible();
    await expect(page.getByTestId('inspector-panel')).toBeVisible();

    const totalFilesText = await page.getByTestId('summary-total-files').textContent();
    expect(Number(totalFilesText?.replace(/,/g, ''))).toBeGreaterThan(15);

    // 4. Select a specific backend file in Explorer and verify Inspector updates
    const analyzerFileBtn = page.getByTestId('explorer-file-backend/repodna/core/analyzer.py');
    await analyzerFileBtn.scrollIntoViewIfNeeded();
    await analyzerFileBtn.click();
    await expect(page.getByTestId('inspector-file-title')).toHaveText(
      'backend/repodna/core/analyzer.py'
    );

    // 5. Switch to Health & Transparency Report tab and verify rule explanations
    await page.getByRole('button', { name: /Health & Transparency Report/i }).click();
    await expect(page.getByTestId('health-report-view')).toBeVisible();
    await expect(
      page.getByRole('heading', { name: /Explainable Rule-Based Architecture Health Report/i })
    ).toBeVisible();

    // 6. Test SSRF / Security rejection in the UI by entering an unsafe URL
    await page.getByRole('button', { name: /GitHub HTTPS/i }).click();
    const targetInput = page.locator('#repo-target-input');
    await targetInput.fill('http://127.0.0.1/internal/secret');
    await page.getByTestId('analyze-submit-btn').click();
    await expect(page.getByTestId('error-alert-banner')).toContainText('UNSAFE_PROTOCOL');

    // 7. Test explicitly labeled Demo Mode
    await page.getByRole('button', { name: /Demo Dataset/i }).click();
    await expect(page.getByTestId('demo-mode-badge')).toBeVisible();
    await expect(page.getByTestId('summary-cycle-count')).toContainText('1 cycles');
  });
});

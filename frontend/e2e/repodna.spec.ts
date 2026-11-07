import { expect, test } from '@playwright/test';

const ARTIFACT_DIR =
  'C:/Users/cihan/.gemini/antigravity/brain/a701aa39-50b3-49a3-8f4f-56daa1b4c267';

test.describe('RepoDNA End-to-End Verification & Workstation Audit', () => {
  test('verifies launchpad, live scan, dark/light themes, Ctrl+K command palette, package clustering, density, responsive layout, and exports', async ({
    page,
  }) => {
    const t0 = Date.now();
    await page.goto('/');

    // 1. Verify no auto-scan occurred; launchpad is visible
    await expect(page.getByTestId('welcome-launchpad')).toBeVisible();
    const initialRenderMs = Date.now() - t0;
    await expect(page.getByRole('heading', { name: 'RepoDNA', exact: true })).toBeVisible();
    await page.screenshot({
      path: `${ARTIFACT_DIR}/repodna-launchpad.png`,
    });

    // 2. Click "Analyze Current Workspace" to run a real live scan on RepoDNA itself
    const scanWorkspaceBtn = page.getByTestId('launchpad-scan-workspace-btn');
    await expect(scanWorkspaceBtn).toBeVisible();
    await scanWorkspaceBtn.click();

    // 3. Verify real scan results populate Summary Strip, Explorer, Graph, and Inspector
    await expect(page.getByTestId('summary-health-score')).toBeVisible({ timeout: 15000 });
    await expect(page.getByTestId('dependency-graph-canvas')).toBeVisible();
    await expect(page.getByTestId('inspector-panel')).toBeVisible();

    const totalFilesText = await page.getByTestId('summary-total-files').textContent();
    expect(Number(totalFilesText?.replace(/,/g, ''))).toBeGreaterThan(15);

    // 4. Select a specific backend file in Explorer and measure interaction latency
    const tSelectStart = Date.now();
    const analyzerFileBtn = page.getByTestId('explorer-file-backend/repodna/core/analyzer.py');
    await analyzerFileBtn.click();
    await expect(page.getByTestId('inspector-file-title')).toHaveText(
      'backend/repodna/core/analyzer.py'
    );
    const selectLatencyMs = Date.now() - tSelectStart;

    // 5. Capture Dark Theme Studio Screenshot
    await page.waitForTimeout(350);
    await page.screenshot({
      path: `${ARTIFACT_DIR}/repodna-studio-live.png`,
    });

    // 6. Test Directory Package Collapse (Grouping Mode) and Density Mode
    const initialNodesCount = Number(
      await page.getByTestId('graph-visible-nodes-count').textContent()
    );
    const tGroupStart = Date.now();
    await page.getByTestId('grouping-directories-btn').click();
    await page.waitForTimeout(250);
    const collapsedNodesCount = Number(
      await page.getByTestId('graph-visible-nodes-count').textContent()
    );
    const groupLatencyMs = Date.now() - tGroupStart;
    expect(collapsedNodesCount).toBeLessThan(initialNodesCount);

    await page.getByTestId('graph-density-select').selectOption('compact');
    await page.getByTestId('grouping-files-btn').click();
    await page.getByTestId('reset-layout-fit-btn').click();

    // 7. Test Command Palette (Ctrl+K) and capture screenshot
    await page.keyboard.press('Control+k');
    await expect(page.getByTestId('command-palette-dialog')).toBeVisible();
    await page.getByTestId('command-palette-input').fill('treesitter_parser');
    await page.waitForTimeout(150);
    await page.screenshot({
      path: `${ARTIFACT_DIR}/repodna-command-palette.png`,
    });
    await page.keyboard.press('Enter');
    await expect(page.getByTestId('inspector-file-title')).toHaveText(
      'backend/repodna/parsers/treesitter_parser.py'
    );

    // 8. Test Light Theme and Dark Theme and capture screenshot
    await page.evaluate(() => {
      const meta = document.querySelector<HTMLMetaElement>('meta[name="color-scheme"]');
      if (meta) meta.content = 'light';
      localStorage.setItem('color-scheme', 'light');
      window.dispatchEvent(new StorageEvent('storage', { key: 'color-scheme', newValue: 'light' }));
    });
    await page.waitForTimeout(250);
    await page.screenshot({
      path: `${ARTIFACT_DIR}/repodna-studio-light.png`,
    });
    // Switch back to Dark Theme via the toggle button
    await page.getByTestId('theme-toggle-btn').click();
    await page.waitForTimeout(150);

    // 9. Switch to Health & Transparency Report tab and capture screenshot
    await page.getByRole('button', { name: /Health & Transparency Report/i }).click();
    await expect(page.getByTestId('health-report-view')).toBeVisible();
    await expect(
      page.getByRole('heading', { name: /Explainable Rule-Based Architecture Health Report/i })
    ).toBeVisible();
    await page.screenshot({
      path: `${ARTIFACT_DIR}/repodna-health-report.png`,
    });

    // 10. Test Report Export User Feedback Flow
    const downloadPromise = page.waitForEvent('download');
    await page.getByRole('link', { name: /Export JSON/i }).click();
    const download = await downloadPromise;
    expect(download.suggestedFilename()).toContain('.json');
    await expect(page.getByTestId('export-status-badge')).toContainText('Exported JSON report');

    // 11. Test SSRF / Security rejection in the UI
    await page.getByRole('button', { name: /GitHub HTTPS/i }).click();
    const targetInput = page.locator('#repo-target-input');
    await targetInput.fill('http://127.0.0.1/internal/secret');
    await page.getByTestId('analyze-submit-btn').click();
    await expect(page.getByTestId('error-alert-banner')).toContainText('UNSAFE_PROTOCOL');

    // 12. Test explicitly labeled Demo Mode + Responsive Mobile Viewport
    await page.getByRole('button', { name: /Demo Dataset/i }).click();
    await expect(page.getByTestId('demo-mode-badge')).toBeVisible();
    await expect(page.getByTestId('summary-cycle-count')).toContainText('1 cycles');

    await page.setViewportSize({ width: 390, height: 844 });
    await page.waitForTimeout(200);
    await expect(page.getByRole('heading', { name: 'RepoDNA', exact: true })).toBeVisible();

    console.log(
      JSON.stringify({
        initialRenderMs,
        selectLatencyMs,
        groupLatencyMs,
        initialNodesCount,
        collapsedNodesCount,
      })
    );
  });
});

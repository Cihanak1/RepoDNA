import { expect, test } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

const artifacts = '../docs/design/after';
test('panel resizing, persistence, focus shortcuts, search, package details and mobile navigation', async ({ page }) => {
  await page.goto('/');
  await page.getByTestId('launchpad-demo-btn').click();
  await expect(page.getByTestId('summary-health-score')).toBeVisible();
  await expect(page.locator('.react-flow__minimap-node')).toHaveCount(7);
  const graphNode = page.locator('.react-flow__node').filter({ has: page.getByTestId('graph-node-src/api/router.py') });
  await graphNode.focus();
  await page.keyboard.press('Enter');
  await expect(page.getByTestId('inspector-file-title')).toHaveText('src/api/router.py');
  await page.getByRole('button', { name: 'Zoom to selection' }).click();
  await page.getByTestId('reset-layout-fit-btn').click();
  const separator = page.getByRole('separator', { name: 'Explorer width' });
  await separator.focus();
  await page.keyboard.press('ArrowRight');
  await expect(separator).toHaveAttribute('aria-valuenow', '276');
  const bounds = await separator.boundingBox();
  await page.mouse.move(bounds!.x + 2, bounds!.y + 30);
  await page.mouse.down(); await page.mouse.move(bounds!.x + 42, bounds!.y + 30); await page.mouse.up();
  await expect(separator).toHaveAttribute('aria-valuenow', '316');
  await page.getByRole('button', { name: 'Focus canvas', exact: true }).click();
  await expect(separator).toBeHidden();
  await expect(page.getByTestId('inspector-panel')).toBeHidden();
  await page.keyboard.press('Escape');
  await expect(separator).toBeVisible();
  await page.keyboard.press('/');
  await expect(page.locator('#explorer-search-input')).toBeFocused();
  await page.locator('#explorer-search-input').fill('payment');
  await expect(page.locator('mark')).toHaveText('payment');
  await expect(page.getByTestId('graph-visible-nodes-count')).toHaveText('2');
  await page.locator('#explorer-search-input').fill('not-a-real-module');
  await expect(page.getByText('No modules in this view')).toBeVisible();
  await page.getByRole('button', { name: 'Reset filters', exact: true }).click();
  await page.getByTestId('grouping-directories-btn').click();
  await expect(page.getByRole('region', { name: 'Selected package' })).toBeVisible();
  await page.getByRole('button', { name: 'Expand package to modules' }).click();
  await expect(page.getByTestId('graph-visible-nodes-count')).toHaveText('7');
  await page.reload();
  await page.getByTestId('launchpad-demo-btn').click();
  await expect(separator).toHaveAttribute('aria-valuenow', '316');
  for (const [width, height] of [[390,844],[768,1024],[1366,768],[1440,900],[1920,1080]]) {
    await page.setViewportSize({ width, height });
    await page.waitForTimeout(400);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await expect(page.getByTestId('dependency-graph-canvas')).toBeInViewport();
    await page.screenshot({ path: `${artifacts}/viewport-${width}.png` });
    if (width < 1024) {
      await page.getByRole('button', { name: 'Files', exact: true }).click();
      await expect(page.locator('#explorer-search-input')).toBeVisible();
      await page.getByTestId('explorer-file-src/api/router.py').click();
      await expect(page.getByTestId('inspector-file-title')).toHaveText('src/api/router.py');
      await page.getByRole('button', { name: 'Canvas', exact: true }).click();
    }
  }
});

test('palette keyboard selection, recent commands, focus restore, clipboard and both exports', async ({ page, context }) => {
  await context.grantPermissions(['clipboard-read', 'clipboard-write']);
  await page.goto('/');
  await page.getByTestId('launchpad-demo-btn').click();
  await expect(page.getByTestId('summary-health-score')).toBeVisible();
  await page.getByRole('button', { name: 'Copy path', exact: true }).click();
  expect(await page.evaluate(() => navigator.clipboard.readText())).toContain('src/');
  await page.getByRole('button', { name: 'Copy metrics' }).click();
  expect(JSON.parse(await page.evaluate(() => navigator.clipboard.readText()))).toHaveProperty('fan_in');
  await page.getByTestId('open-command-palette-btn').click();
  await expect(page.getByRole('combobox', { name: 'Search commands or modules' })).toBeFocused();
  await page.getByRole('combobox', { name: 'Search commands or modules' }).fill('Toggle Dark');
  await page.keyboard.press('Enter');
  await expect(page.getByTestId('command-palette-dialog')).toBeHidden();
  await expect(page.getByTestId('open-command-palette-btn')).toBeFocused();
  await page.keyboard.press('Control+k');
  await expect(page.getByTestId('command-palette-dialog').getByRole('option').first()).toContainText('Recent');
  await page.keyboard.press('ArrowDown');
  await expect(page.getByRole('combobox', { name: 'Search commands or modules' })).toHaveAttribute('aria-activedescendant', 'command-option-1');
  await page.keyboard.press('Escape');
  for (const format of ['JSON','HTML']) {
    const download = page.waitForEvent('download');
    await page.getByRole('link', { name: `Export ${format}` }).click();
    const file = await download;
    expect(await file.failure()).toBeNull();
    expect(file.suggestedFilename()).toContain(format.toLowerCase());
  }
});

test('visible error recovery and cancellation preserve the previous analysis', async ({ page }) => {
  await page.goto('/');
  await page.getByTestId('launchpad-demo-btn').click();
  await expect(page.getByTestId('summary-health-score')).toBeVisible();
  await page.getByRole('button', { name: 'Change repository', exact: true }).click();
  await page.getByRole('button', { name: 'GitHub HTTPS', exact: true }).click();
  await page.locator('#repo-target-input').fill('http://127.0.0.1/private');
  await page.getByTestId('analyze-submit-btn').click();
  await expect(page.getByTestId('error-alert-banner')).toContainText('UNSAFE_PROTOCOL');
  expect((await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa','wcag22aa']).analyze()).violations).toEqual([]);
  await page.screenshot({ path: `${artifacts}/error.png` });
  await page.getByRole('button', { name: 'Dismiss', exact: true }).click();
  // Delay real progress delivery, retaining actual job creation and cancellation endpoints.
  await page.route('**/api/jobs/*', async route => {
    if (route.request().method() === 'GET' && !route.request().url().endsWith('/result')) {
      await new Promise(resolve => setTimeout(resolve, 1200));
    }
    await route.continue();
  });
  await page.locator('#repo-target-input').fill('https://github.com/Cihanak1/NiceWP');
  await page.getByTestId('analyze-submit-btn').click();
  await expect(page.getByRole('button', { name: 'Cancel Scan' })).toBeVisible();
  await page.screenshot({ path: `${artifacts}/loading-cancel.png` });
  await page.getByRole('button', { name: 'Cancel Scan' }).click();
  await expect(page.getByRole('button', { name: 'Cancel Scan' })).toBeHidden();
  await expect(page.getByTestId('demo-mode-badge')).toBeVisible();
  await expect(page.getByTestId('previous-analysis-banner')).toBeHidden();
});

import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

test('WCAG A/AA automated checks across themes, report, palette and mobile', async ({ page }) => {
  test.setTimeout(90000);
  const audit = async (name: string) => {
    const result = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa', 'wcag22aa']).analyze();
    expect(result.violations.map(v => ({ id: v.id, nodes: v.nodes.map(n => ({ target:n.target, message:n.failureSummary })) })), name).toEqual([]);
  };
  await page.goto('/');
  await audit('launchpad');
  await page.getByTestId('launchpad-demo-btn').click();
  await expect(page.getByTestId('summary-health-score')).toBeVisible();
  for (const theme of ['dark','light']) {
    await page.evaluate(theme => {
      document.querySelector('meta[name="color-scheme"]')?.setAttribute('content',theme);
      localStorage.setItem('color-scheme',theme);
      window.dispatchEvent(new StorageEvent('storage',{key:'color-scheme',newValue:theme}));
    }, theme);
    await page.waitForTimeout(400);
    await audit(`${theme} studio`);
    await page.screenshot({path:`../docs/design/after/studio-${theme}.png`});
    await page.getByRole('button',{name:'Health & Transparency Report',exact:true}).click();
    await audit(`${theme} report`);
    await page.getByRole('button',{name:'Architecture Studio',exact:true}).click();
  }
  await page.keyboard.press('Control+k');
  await audit('palette');
  await page.keyboard.press('Escape');
  await page.setViewportSize({width:390,height:844});
  await page.waitForTimeout(400);
  await audit('mobile');
});

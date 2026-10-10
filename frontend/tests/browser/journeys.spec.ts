import { test, expect, type Page } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
async function correct(page: Page) {
  await page.goto('/app/jobs/sample-review');
  await page.getByRole('button', { name: 'Edit Fake café, grocery' }).click();
  await page.getByLabel('Debit', { exact: true }).fill('12.50');
  await page.getByRole('button', { name: 'Stage change', exact: true }).click();
  await expect(page.getByText('1 staged change(s)')).toBeVisible();
  await page.getByRole('button', { name: 'Save staged changes' }).click();
  await expect(page.getByText('Reconciles after corrections.')).toBeVisible();
}
async function compare(page: Page) {
  await page.getByRole('tab', { name: 'Checks', exact: true }).click();
  await page.getByRole('checkbox', { name: /Compared 2026-01-02/ }).check();
  await page.getByRole('checkbox', { name: /Compared 2026-01-03/ }).check();
  await page
    .getByLabel('Source-check note')
    .fill('Compared dates, descriptions and money with both fictional source rows');
  await page.getByRole('button', { name: 'Record source check' }).click();
  await expect(page.getByText(/Current check:/)).toBeVisible();
}
test('correct, check and prepare six reference formats and package', async ({ page }) => {
  await correct(page);
  await compare(page);
  await page.getByRole('tab', { name: 'Exports', exact: true }).click();
  await page.getByRole('button', { name: 'Prepare preview package', exact: true }).click();
  await expect(page.getByRole('link', { name: /Download fixed .* sample$/ })).toHaveCount(6);
  const download = page.waitForEvent('download');
  await page.getByRole('link', { name: 'Download fixed sample package' }).click();
  expect((await download).suggestedFilename()).toBe('sample-package.zip');
});
test('blocks exports until review and source checks finish', async ({ page }) => {
  await page.goto('/app/jobs/sample-review');
  await page.getByRole('tab', { name: 'Exports', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Prepare preview package' })).toBeDisabled();
  await expect(page.getByText('Finish the review before preparing exports.')).toBeVisible();
});
test('warns before discarding staged changes on a tab switch', async ({ page }) => {
  await page.goto('/app/jobs/sample-review');
  await page.getByRole('button', { name: 'Edit Fake café, grocery' }).click();
  await page.getByLabel('Debit', { exact: true }).fill('12.50');
  await page.getByRole('button', { name: 'Stage change', exact: true }).click();
  await page.getByRole('tab', { name: 'Checks', exact: true }).click();
  await expect(page.getByRole('dialog', { name: 'Discard staged changes?' })).toBeVisible();
  await page.getByRole('button', { name: 'Discard and continue' }).click();
  await page.getByRole('tab', { name: 'Review', exact: true }).click();
  await expect(page.getByText('12.59', { exact: true })).toBeVisible();
  await expect(page.getByText('1 staged change(s)')).toHaveCount(0);
});
test('intake is guided and selected files are not posted', async ({ page }) => {
  const posted: string[] = [];
  page.on('request', (r) => {
    if (r.method() === 'POST') posted.push(r.url());
  });
  await page.goto('/app/new');
  await expect(page.getByRole('button', { name: 'Continue', exact: true })).toBeDisabled();
  await page.getByRole('button', { name: 'Use bundled synthetic statement' }).click();
  await page.getByRole('checkbox', { name: /These are fictional samples/ }).check();
  await page.getByRole('button', { name: 'Continue', exact: true }).click();
  await page.getByRole('button', { name: 'Continue', exact: true }).click();
  await page.getByRole('button', { name: 'Create practice conversion' }).click();
  await page.getByRole('button', { name: 'Start practice processing' }).click();
  await expect(page.getByRole('button', { name: 'Edit Fake café, grocery' })).toBeEnabled();
  expect(posted).toEqual([]);
  await page.getByRole('tab', { name: 'Activity', exact: true }).click();
  await expect(
    page.getByText('Synthetic fixture applied. This is not OCR of the selected file.'),
  ).toBeVisible();
});
test('merge needs explicit account confirmation', async ({ page }) => {
  await page.goto('/app/new');
  await page.getByRole('button', { name: 'Use bundled synthetic statement' }).click();
  await page.getByRole('checkbox', { name: /These are fictional/ }).check();
  await page.getByRole('button', { name: 'Continue', exact: true }).click();
  await page.getByRole('checkbox', { name: /Merge statements/ }).check();
  await page.getByRole('button', { name: 'Continue', exact: true }).click();
  await page.getByRole('button', { name: 'Create practice conversion' }).click();
  await expect(page.getByRole('alert')).toHaveText(
    'Confirm a private account group before merging.',
  );
});
test('AI source confirmation stays distinct from fixing amounts', async ({ page }) => {
  await page.goto('/app/jobs/sample-scanned');
  await page.getByRole('tab', { name: 'Checks', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Record source check' })).toBeDisabled();
  await page.getByRole('checkbox', { name: /I compared every AI sample row/ }).check();
  await page.getByRole('button', { name: 'Confirm AI sample source' }).click();
  await expect(page.getByText(/AI source confirmation recorded/)).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Numbers reconcile' })).toBeVisible();
});
test('consent needs a note and never contacts an external provider', async ({ page }) => {
  const external: string[] = [];
  page.on('request', (r) => {
    if (!r.url().startsWith('http://127.0.0.1:4173')) external.push(r.url());
  });
  await page.goto('/app/jobs/sample-scanned');
  await page.getByRole('tab', { name: 'Optional AI', exact: true }).click();
  await page.getByRole('checkbox', { name: /Permission to use/ }).check();
  await expect(page.getByRole('button', { name: 'Save preview consent' })).toBeDisabled();
  await page
    .getByLabel('Consent record')
    .fill('Fictional client approved the sample provider today');
  await page.getByRole('button', { name: 'Save preview consent' }).click();
  await expect(page.getByRole('button', { name: /Run AI fallback/ })).toBeDisabled();
  expect(external).toEqual([]);
});
test('BYOK picker defaults to Max for documented fixture and default for unknown', async ({
  page,
}) => {
  await page.goto('/app/connections');
  await page.getByRole('button', { name: 'Edit connection' }).click();
  await expect(page.getByLabel('API key (secure backend required)')).toBeDisabled();
  await page.getByLabel('Model picker').selectOption('documented-sample-model');
  await expect(page.getByLabel('Reasoning effort')).toHaveValue('max');
  await page.getByLabel('Model picker').selectOption('unknown-capability-model');
  await expect(page.getByLabel('Reasoning effort')).toHaveValue('provider_default');
  await expect(page.getByLabel('Reasoning effort').locator('option')).toHaveCount(1);
  await page.getByRole('button', { name: 'Save preview connection' }).click();
  await expect(page.getByRole('dialog')).toHaveCount(0);
});
test('supports custom HTTPS connection and manual model without invented capabilities', async ({
  page,
}) => {
  await page.goto('/app/connections');
  await page.getByRole('button', { name: 'Add connection', exact: true }).click();
  await page.getByLabel('Connection nickname').fill('My custom provider');
  await page.getByLabel('API base URL').fill('https://my-provider.example/v1');
  await page.getByText('Add a model manually', { exact: true }).click();
  await page.getByLabel('Manual model ID').fill('my-model');
  await page.getByRole('button', { name: 'Add model to picker' }).click();
  await expect(page.getByLabel('Reasoning effort')).toHaveValue('provider_default');
  await page.getByRole('button', { name: 'Save preview connection' }).click();
  await expect(page.getByRole('heading', { name: 'My custom provider' })).toBeVisible();
});
test('partial removal has no certificate, retry scrubs data', async ({ page }) => {
  await page.goto('/app/jobs/sample-ready');
  await page.getByRole('tab', { name: 'Data & privacy' }).click();
  await page.getByRole('button', { name: 'Remove preview data' }).click();
  await expect(page.getByRole('button', { name: 'Confirm removal' })).toBeDisabled();
  await page.getByRole('checkbox', { name: /I understand this removes/ }).check();
  await page.getByRole('checkbox', { name: /Demonstrate a partial failure/ }).check();
  await page.getByRole('button', { name: 'Confirm removal' }).click();
  await expect(page.getByText(/No certificate was issued/)).toBeVisible();
  await page.getByRole('button', { name: 'Retry removal' }).click();
  await page.getByRole('checkbox', { name: /Demonstrate a partial failure/ }).uncheck();
  await page.getByRole('button', { name: 'Confirm removal' }).click();
  await expect(page.getByRole('heading', { name: 'Removed conversion' })).toBeVisible();
  await expect(page.getByText(/not a real deletion certificate/)).toBeVisible();
  await expect(page.getByText('Fake salary', { exact: true })).toHaveCount(0);
});
test('owner navigation is separate and recovery works', async ({ page }) => {
  await page.goto('/admin');
  await expect(page.getByRole('heading', { name: 'Owner tools' })).toBeVisible();
  await page.getByLabel('Preview role').selectOption('admin');
  await expect(page.getByRole('tab', { name: 'Health & models' })).toBeVisible();
  await page.getByRole('tab', { name: 'Health & models' }).click();
  await page.getByRole('button', { name: 'Show local diagnostic commands' }).click();
  await expect(page.getByText('stmtconv doctor', { exact: true })).toBeVisible();
  await page.goto('/app/jobs/sample-failed');
  await page.getByRole('button', { name: 'Retry practice processing' }).click();
  await expect(page.getByRole('button', { name: 'Edit Fake café, grocery' })).toBeEnabled();
});
test('dialog keyboard focus, escape and category editing', async ({ page }) => {
  await page.goto('/app/jobs/sample-review');
  await page.getByRole('button', { name: 'Edit Fake café, grocery' }).click();
  await expect(page.getByRole('dialog')).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Edit Fake café, grocery' })).toBeFocused();
  await page.goto('/app/categories');
  await page.getByRole('button', { name: 'Add rule' }).click();
  await page.getByLabel('Category', { exact: true }).last().fill('Transport');
  await page.getByLabel('Keyword or regex').last().fill('bus');
  await page.getByRole('button', { name: 'Save category rules' }).click();
  await expect(page.getByText('Category rules saved in this preview session.')).toBeVisible();
});
const routes = [
  '/',
  '/demo',
  '/pricing',
  '/help',
  '/sign-in',
  '/invite',
  '/app',
  '/app/new',
  '/app/jobs',
  '/app/jobs/sample-review',
  '/app/connections',
  '/app/categories',
  '/app/settings',
  '/admin',
];
for (const width of [1440, 375])
  test(`routes have no accessibility violations or horizontal page overflow at ${width}px`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 950 });
    for (const route of routes) {
      await page.goto(route);
      if (route === '/admin') await page.getByLabel('Preview role').selectOption('admin');
      await expect(page.locator('h1')).toBeVisible();
      expect(
        await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
        route,
      ).toBe(true);
      const results = await new AxeBuilder({ page })
        .withTags(['wcag2a', 'wcag2aa', 'wcag21aa'])
        .analyze();
      expect(
        results.violations,
        `${width} ${route}: ${JSON.stringify(results.violations.map((v) => ({ id: v.id, nodes: v.nodes.map((n) => n.target) })))}`,
      ).toEqual([]);
      if (['/', '/app/jobs/sample-review', '/app/connections', '/admin'].includes(route))
        await page.screenshot({
          path: `test-results/previews/${width}-${route === '/' ? 'home' : route.replaceAll('/', '-').slice(1)}.png`,
          fullPage: true,
        });
    }
  });
test('wide conversions table stays within the phone and its final column is reachable', async ({
  page,
}) => {
  await page.setViewportSize({ width: 375, height: 950 });
  await page.goto('/app');
  const region = page.getByRole('region', { name: 'Conversions table' });
  await expect(region).toBeVisible();
  // Wide columns also exercise absolutely positioned screen-reader-only headers.
  await page.addStyleTag({ content: '.table-scroll table { min-width: 750px; }' });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(
    true,
  );
  expect(await region.evaluate((node) => node.scrollWidth > node.clientWidth)).toBe(true);
  await region.evaluate((node) => {
    node.scrollLeft = node.scrollWidth;
  });
  const open = region.getByRole('link', { name: 'Open January · bank account 1234' });
  await expect(open).toBeInViewport();
  await open.click();
  await expect(page).toHaveURL(/\/app\/jobs\/sample-review/);
});
test('mobile menu opens and review tab persists on refresh', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await page.goto('/app');
  await page.getByRole('button', { name: 'Open navigation' }).click();
  await page.getByRole('dialog').getByRole('link', { name: 'AI connections' }).click();
  await expect(
    page.getByRole('heading', { name: 'Your models, connected your way' }),
  ).toBeVisible();
  await page.goto('/app/jobs/sample-review');
  await page.getByRole('tab', { name: 'Files & intake' }).click();
  await page.reload();
  await expect(page.getByRole('tab', { name: 'Files & intake' })).toHaveAttribute(
    'data-state',
    'active',
  );
});
test('review tabs and provider dialogs pass accessibility checks', async ({ page }) => {
  await page.goto('/app/jobs/sample-review');
  for (const tab of [
    'Review',
    'Checks',
    'Exports',
    'Files & intake',
    'Optional AI',
    'Activity',
    'Data & privacy',
  ]) {
    await page.getByRole('tab', { name: tab, exact: true }).click();
    expect(
      (await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze())
        .violations,
      tab,
    ).toEqual([]);
  }
  await page.goto('/app/connections');
  await page.getByRole('button', { name: 'Edit connection' }).click();
  expect(
    (await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze())
      .violations,
  ).toEqual([]);
});

test('saved defaults apply to new intake, reset restores the preview and filters survive reload', async ({
  page,
}) => {
  await page.goto('/app/settings');
  await page.getByLabel('Default currency').fill('EUR');
  await page.getByRole('button', { name: 'Save preferences' }).click();
  await page.getByRole('link', { name: 'New conversion', exact: true }).click();
  await page.getByRole('button', { name: 'Use bundled synthetic statement' }).click();
  await page.getByRole('checkbox', { name: /These are fictional/ }).check();
  await page.getByRole('button', { name: 'Continue', exact: true }).click();
  await expect(page.getByLabel('Currency', { exact: true })).toHaveValue('EUR');
  await page.getByRole('link', { name: 'Settings', exact: true }).click();
  await page.getByRole('button', { name: 'Reset sample workspace' }).click();
  await expect(page.getByLabel('Default currency')).toHaveValue('USD');
  await page.getByRole('link', { name: 'Conversions', exact: true }).click();
  await page.getByLabel('Search conversions').fill('January');
  await page.reload();
  await expect(page.getByLabel('Search conversions')).toHaveValue('January');
  await expect(
    page.getByRole('link', { name: 'January · bank account 1234', exact: true }),
  ).toBeVisible();
});

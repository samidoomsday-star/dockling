import { test, expect } from '@playwright/test';
test('home renders and opens review', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('heading', { name: /From statement clutter/ })).toBeVisible();
  await page.getByRole('link', { name: 'Try the guided sample' }).click();
  await expect(page.getByRole('tab', { name: 'Review', exact: true })).toBeVisible();
});

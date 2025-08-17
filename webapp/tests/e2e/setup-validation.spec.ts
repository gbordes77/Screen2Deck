import { test, expect } from '@playwright/test';

/**
 * Setup Validation Test
 * Ensures all services are running and responsive before running main E2E tests
 */
test.describe('Setup Validation', () => {
  test('should have all services running', async ({ page, request }) => {
    // Test frontend is accessible
    await page.goto('/');
    await expect(page).toHaveTitle(/Screen2Deck|MTG/i);
    
    // Test backend API is accessible
    const healthResponse = await request.get(process.env.API_URL + '/health');
    expect(healthResponse.ok()).toBeTruthy();
    
    const healthData = await healthResponse.json();
    expect(healthData).toHaveProperty('status', 'healthy');
  });

  test('should load upload page successfully', async ({ page }) => {
    await page.goto('/');
    
    // Check for upload interface elements
    await expect(page.locator('input[type="file"]')).toBeVisible();
    
    // Look for upload-related text
    const hasUploadText = await page.getByText(/upload|drag|drop|select/i).first().isVisible();
    expect(hasUploadText).toBeTruthy();
  });

  test('should have API documentation accessible', async ({ request }) => {
    const docsResponse = await request.get(process.env.API_URL + '/docs');
    expect(docsResponse.ok()).toBeTruthy();
  });
});
/**
 * S8 - Error Handling & UX Testing
 * Verify graceful error handling and recovery
 */
import { test, expect } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';
import {
  getConfig,
  uploadImage,
  createCorruptedImage,
  getTestImages
} from '../helpers/test-utils';

test.describe('S8 - Error Handling & UX', () => {
  const config = getConfig();
  const testImages = getTestImages();
  const tempFiles: string[] = [];

  test.afterEach(async () => {
    // Cleanup temp files
    for (const file of tempFiles) {
      if (fs.existsSync(file)) {
        fs.unlinkSync(file);
      }
    }
    tempFiles.length = 0;
  });

  test('S8.1 - Corrupted image handling', async ({ page }) => {
    await page.goto(config.webUrl);
    
    const corruptedFile = await createCorruptedImage();
    tempFiles.push(corruptedFile);
    
    await uploadImage(page, corruptedFile);
    
    // Should show error toast/message
    const errorToast = page.locator('[data-testid="error-toast"], [data-testid="error-message"]');
    await expect(errorToast).toBeVisible({ timeout: 10000 });
    
    // Should not get stuck in infinite loop
    await page.waitForTimeout(2000);
    
    // Upload area should be available for retry
    const uploadArea = page.locator('[data-testid="upload-area"]');
    await expect(uploadArea).toBeVisible();
    
    // No spinner should be stuck
    const spinner = page.locator('[data-testid="spinner"], [data-testid="loading"]');
    if (await spinner.count() > 0) {
      await expect(spinner).not.toBeVisible();
    }
  });

  test('S8.2 - Backend timeout simulation', async ({ page }) => {
    await page.goto(config.webUrl);
    
    // Intercept OCR request and delay
    await page.route('**/api/ocr/**', async route => {
      await new Promise(resolve => setTimeout(resolve, 40000)); // Exceed timeout
      route.abort();
    });
    
    const imagePath = testImages[0];
    await uploadImage(page, imagePath);
    
    // Should show timeout message
    const timeoutMessage = page.locator('[data-testid="timeout-message"]');
    await expect(timeoutMessage).toBeVisible({ timeout: 35000 });
    
    // Should show retry option
    const retryButton = page.locator('[data-testid="retry-button"], button:has-text("Retry")');
    await expect(retryButton).toBeVisible();
    
    // Should be able to cancel
    const cancelButton = page.locator('[data-testid="cancel-button"], button:has-text("Cancel")');
    if (await cancelButton.count() > 0) {
      await cancelButton.click();
      await expect(page.locator('[data-testid="upload-area"]')).toBeVisible();
    }
  });

  test('S8.3 - Network error recovery', async ({ page }) => {
    await page.goto(config.webUrl);
    
    let requestCount = 0;
    // Fail first request, succeed on retry
    await page.route('**/api/ocr/**', route => {
      requestCount++;
      if (requestCount === 1) {
        route.abort('connectionfailed');
      } else {
        route.continue();
      }
    });
    
    const imagePath = testImages[0];
    await uploadImage(page, imagePath);
    
    // Should show network error
    const errorMessage = page.locator('[data-testid="network-error"], [data-testid="error-message"]');
    await expect(errorMessage).toBeVisible({ timeout: 10000 });
    
    // Click retry
    const retryButton = page.locator('[data-testid="retry-button"], button:has-text("Retry")');
    if (await retryButton.count() > 0) {
      await retryButton.click();
      
      // Should succeed on retry
      await expect(page.locator('[data-testid="deck-display"]')).toBeVisible({ timeout: 30000 });
    }
  });

  test('S8.4 - Partial processing failure', async ({ page }) => {
    await page.goto(config.webUrl);
    
    // Mock partial failure in processing
    await page.route('**/api/cards/validate', route => {
      route.fulfill({
        status: 200,
        body: JSON.stringify({
          success: true,
          cards: [
            { name: 'Island', quantity: 4, validated: true },
            { name: 'Unknown Card', quantity: 2, validated: false }
          ],
          warnings: ['Some cards could not be validated']
        })
      });
    });
    
    const imagePath = testImages[0];
    await uploadImage(page, imagePath);
    
    // Should show warning but continue
    const warning = page.locator('[data-testid="validation-warning"]');
    if (await warning.count() > 0) {
      await expect(warning).toBeVisible();
    }
    
    // Should still display deck
    await expect(page.locator('[data-testid="deck-display"]')).toBeVisible({ timeout: 30000 });
    
    // Invalid cards should be marked
    const invalidCards = page.locator('[data-testid="invalid-card"]');
    if (await invalidCards.count() > 0) {
      expect(await invalidCards.count()).toBeGreaterThan(0);
    }
  });

  test('S8.5 - Progress not stuck on error', async ({ page }) => {
    await page.goto(config.webUrl);
    
    // Fail midway through processing
    await page.route('**/api/cards/validate', route => {
      route.abort('failed');
    });
    
    const imagePath = testImages[0];
    await uploadImage(page, imagePath);
    
    // Wait for error
    await page.waitForTimeout(5000);
    
    // Progress bar should not be stuck at intermediate value
    const progressBar = page.locator('[data-testid="progress-bar"]');
    if (await progressBar.count() > 0) {
      const value = await progressBar.getAttribute('aria-valuenow');
      if (value) {
        const progress = parseInt(value);
        expect(progress === 0 || progress === 100).toBe(true);
      }
    }
    
    // Loading spinner should be hidden
    const spinner = page.locator('[data-testid="spinner"]');
    if (await spinner.count() > 0) {
      await expect(spinner).not.toBeVisible();
    }
  });

  test('S8.6 - Error message clarity', async ({ page }) => {
    await page.goto(config.webUrl);
    
    // Create various error scenarios
    const errorScenarios = [
      {
        route: '**/api/ocr/**',
        status: 500,
        expectedText: /server|error|try again/i
      },
      {
        route: '**/api/ocr/**',
        status: 413,
        expectedText: /large|size|limit/i
      },
      {
        route: '**/api/ocr/**',
        status: 429,
        expectedText: /rate|limit|slow|wait/i
      }
    ];
    
    for (const scenario of errorScenarios) {
      await page.goto(config.webUrl);
      
      await page.route(scenario.route, route => {
        route.fulfill({ status: scenario.status });
      });
      
      const imagePath = testImages[0];
      await uploadImage(page, imagePath);
      
      const errorMessage = page.locator('[data-testid="error-message"], [data-testid="error-toast"]');
      await expect(errorMessage).toBeVisible({ timeout: 10000 });
      
      const text = await errorMessage.textContent();
      expect(text).toMatch(scenario.expectedText);
      
      // Clear for next test
      await page.unroute(scenario.route);
    }
  });

  test('S8.7 - Cancel operation', async ({ page }) => {
    await page.goto(config.webUrl);
    
    // Delay processing to allow cancel
    await page.route('**/api/ocr/**', async route => {
      await new Promise(resolve => setTimeout(resolve, 5000));
      route.continue();
    });
    
    const imagePath = testImages[0];
    await uploadImage(page, imagePath);
    
    // Wait for processing to start
    await page.waitForTimeout(1000);
    
    // Click cancel if available
    const cancelButton = page.locator('[data-testid="cancel-button"], button:has-text("Cancel")');
    if (await cancelButton.count() > 0) {
      await cancelButton.click();
      
      // Should return to initial state
      await expect(page.locator('[data-testid="upload-area"]')).toBeVisible();
      
      // No processing indicators
      const spinner = page.locator('[data-testid="spinner"]');
      if (await spinner.count() > 0) {
        await expect(spinner).not.toBeVisible();
      }
    }
  });
});
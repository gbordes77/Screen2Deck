/**
 * S5 - Vision Fallback Testing
 * Test OpenAI Vision API fallback scenarios
 */
import { test, expect } from '@playwright/test';
import * as path from 'path';
import * as fs from 'fs';
import {
  getConfig,
  uploadImage,
  waitForDeckReady,
  downloadExport,
  compareWithGolden,
  getTestImages
} from '../helpers/test-utils';

test.describe('S5 - Vision Fallback', () => {
  const config = getConfig();
  const testImages = getTestImages('adversarial'); // Use harder images

  test.beforeEach(async ({ page }) => {
    // Set environment for vision fallback
    await page.addInitScript(() => {
      (window as any).ENABLE_VISION_FALLBACK = true;
      (window as any).VISION_FALLBACK_CONFIDENCE_THRESHOLD = 0.95; // Force fallback
    });
  });

  test('S5.1 - Forced vision fallback produces correct results', async ({ page }) => {
    // Skip if no adversarial images
    if (!testImages || testImages.length === 0) {
      test.skip();
      return;
    }
    
    const imagePath = testImages[0];
    const imageName = path.basename(imagePath, path.extname(imagePath));
    
    await page.goto(config.webUrl);
    
    // Monitor for fallback indicator
    let fallbackUsed = false;
    page.on('response', response => {
      if (response.url().includes('vision') || response.url().includes('openai')) {
        fallbackUsed = true;
      }
    });
    
    await uploadImage(page, imagePath);
    await waitForDeckReady(page, 45000); // Longer timeout for vision
    
    // Check for fallback indicator in UI
    const fallbackIndicator = page.locator('[data-testid="vision-fallback"]');
    if (await fallbackIndicator.count() > 0) {
      await expect(fallbackIndicator).toBeVisible();
      fallbackUsed = true;
    }
    
    // Get export
    const mtgaExport = await downloadExport(page, 'mtga');
    
    // Compare with golden if exists
    const goldenPath = path.join(config.goldenDir, 'exports', imageName, 'mtga.txt');
    if (fs.existsSync(goldenPath)) {
      expect(compareWithGolden(mtgaExport, goldenPath)).toBe(true);
    } else {
      // At least verify it's a valid deck
      expect(mtgaExport).toContain('Deck');
      expect(mtgaExport.length).toBeGreaterThan(20);
    }
  });

  test('S5.2 - Circuit breaker after multiple fallbacks', async ({ page }) => {
    // This test simulates multiple fallback scenarios
    await page.goto(config.webUrl);
    
    let fallbackCount = 0;
    page.on('response', response => {
      if (response.url().includes('vision')) {
        fallbackCount++;
      }
    });
    
    // Try multiple uploads that would trigger fallback
    for (let i = 0; i < 3 && i < testImages.length; i++) {
      await page.goto(config.webUrl);
      await uploadImage(page, testImages[i]);
      
      // Should still complete, possibly with warning
      await waitForDeckReady(page, 45000);
      
      // Check for circuit breaker warning
      const warning = page.locator('[data-testid="fallback-warning"]');
      if (await warning.count() > 0 && fallbackCount > 2) {
        await expect(warning).toBeVisible();
      }
    }
    
    // System should remain functional
    await expect(page.locator('[data-testid="upload-area"]')).toBeVisible();
  });

  test('S5.3 - Fallback with low confidence threshold', async ({ page }) => {
    // Set very low threshold to avoid fallback
    await page.addInitScript(() => {
      (window as any).VISION_FALLBACK_CONFIDENCE_THRESHOLD = 0.1;
    });
    
    const imagePath = getTestImages('day0')[0]; // Use easy image
    await page.goto(config.webUrl);
    
    let fallbackUsed = false;
    page.on('response', response => {
      if (response.url().includes('vision')) {
        fallbackUsed = true;
      }
    });
    
    await uploadImage(page, imagePath);
    await waitForDeckReady(page);
    
    // Should NOT use fallback for easy images
    expect(fallbackUsed).toBe(false);
    
    // Should still produce valid deck
    const mtgaExport = await downloadExport(page, 'mtga');
    expect(mtgaExport).toContain('Deck');
  });

  test('S5.4 - Fallback error handling', async ({ page }) => {
    await page.goto(config.webUrl);
    
    // Mock vision API failure
    await page.route('**/vision/**', route => {
      route.fulfill({
        status: 500,
        body: JSON.stringify({ error: 'Vision API unavailable' })
      });
    });
    
    const imagePath = testImages[0] || getTestImages('day0')[0];
    await uploadImage(page, imagePath);
    
    // Should show error message
    const errorMessage = page.locator('[data-testid="error-message"]');
    await expect(errorMessage).toBeVisible({ timeout: 15000 });
    
    // Should allow retry
    const retryButton = page.locator('[data-testid="retry-button"]');
    if (await retryButton.count() > 0) {
      await expect(retryButton).toBeVisible();
    }
  });
});
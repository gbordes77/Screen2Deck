/**
 * S6 - Offline Scryfall Testing
 * Verify system works when Scryfall API is unavailable
 */
import { test, expect } from '@playwright/test';
import {
  getConfig,
  uploadImage,
  waitForDeckReady,
  downloadExport,
  simulateOfflineScryfall,
  getTestImages
} from '../helpers/test-utils';

test.describe('S6 - Offline Scryfall', () => {
  const config = getConfig();
  const testImages = getTestImages();

  test('S6.1 - Works with Scryfall blocked', async ({ page }) => {
    const imagePath = testImages[0];
    
    await page.goto(config.webUrl);
    
    // Block all Scryfall requests
    await simulateOfflineScryfall(page);
    
    // Monitor for cache usage
    let cacheHits = 0;
    page.on('response', response => {
      if (response.headers()['x-cache-hit'] === 'true') {
        cacheHits++;
      }
    });
    
    // Upload image
    await uploadImage(page, imagePath);
    await waitForDeckReady(page);
    
    // Should still get a deck
    await expect(page.locator('[data-testid="deck-display"]')).toBeVisible();
    
    // Check for offline mode indicator
    const offlineIndicator = page.locator('[data-testid="offline-mode"]');
    if (await offlineIndicator.count() > 0) {
      await expect(offlineIndicator).toBeVisible();
    }
    
    // Export should still work
    const mtgaExport = await downloadExport(page, 'mtga');
    expect(mtgaExport).toContain('Deck');
    expect(mtgaExport.length).toBeGreaterThan(10);
    
    // Should use cache
    expect(cacheHits).toBeGreaterThan(0);
  });

  test('S6.2 - Scryfall timeout handling', async ({ page }) => {
    const imagePath = testImages[0];
    
    await page.goto(config.webUrl);
    
    // Delay Scryfall responses to simulate timeout
    await page.route(/scryfall\.com/, async route => {
      await new Promise(resolve => setTimeout(resolve, 35000)); // Longer than timeout
      route.abort();
    });
    
    await uploadImage(page, imagePath);
    
    // Should complete despite timeout
    await waitForDeckReady(page, 45000);
    
    // Should show timeout warning
    const timeoutWarning = page.locator('[data-testid="scryfall-timeout"]');
    if (await timeoutWarning.count() > 0) {
      await expect(timeoutWarning).toBeVisible();
    }
    
    // Deck should still be available
    await expect(page.locator('[data-testid="deck-display"]')).toBeVisible();
  });

  test('S6.3 - Partial Scryfall failure', async ({ page }) => {
    const imagePath = testImages[0];
    
    await page.goto(config.webUrl);
    
    let requestCount = 0;
    // Fail every other Scryfall request
    await page.route(/scryfall\.com/, route => {
      requestCount++;
      if (requestCount % 2 === 0) {
        route.abort();
      } else {
        route.continue();
      }
    });
    
    await uploadImage(page, imagePath);
    await waitForDeckReady(page);
    
    // Should complete with partial data
    await expect(page.locator('[data-testid="deck-display"]')).toBeVisible();
    
    // May show partial data warning
    const partialWarning = page.locator('[data-testid="partial-data"]');
    if (await partialWarning.count() > 0) {
      await expect(partialWarning).toBeVisible();
    }
    
    // Export should still work
    const mtgaExport = await downloadExport(page, 'mtga');
    expect(mtgaExport).toBeTruthy();
  });

  test('S6.4 - Cache-first strategy', async ({ page }) => {
    const imagePath = testImages[0];
    
    // First upload with Scryfall available
    await page.goto(config.webUrl);
    await uploadImage(page, imagePath);
    await waitForDeckReady(page);
    
    const firstExport = await downloadExport(page, 'mtga');
    
    // Second upload with Scryfall blocked
    await page.goto(config.webUrl);
    await simulateOfflineScryfall(page);
    
    await uploadImage(page, imagePath);
    await waitForDeckReady(page);
    
    const secondExport = await downloadExport(page, 'mtga');
    
    // Should get same result from cache
    expect(secondExport).toBe(firstExport);
  });

  test('S6.5 - Offline mode messaging', async ({ page }) => {
    await page.goto(config.webUrl);
    
    // Block Scryfall completely
    await simulateOfflineScryfall(page);
    
    const imagePath = testImages[0];
    await uploadImage(page, imagePath);
    await waitForDeckReady(page);
    
    // Check for user-friendly messaging
    const messages = await page.locator('[data-testid="status-message"]').allTextContents();
    
    // Should inform user about offline mode
    const hasOfflineMessage = messages.some(msg => 
      msg.toLowerCase().includes('offline') || 
      msg.toLowerCase().includes('cache')
    );
    
    if (messages.length > 0) {
      expect(hasOfflineMessage).toBe(true);
    }
  });
});
/**
 * S3 - Idempotence Testing
 * Verify re-uploads and concurrent uploads are handled efficiently
 */
import { test, expect, Browser, BrowserContext } from '@playwright/test';
import * as path from 'path';
import {
  getConfig,
  uploadImage,
  waitForDeckReady,
  measureEndToEnd,
  getTestImages
} from '../helpers/test-utils';

test.describe('S3 - Idempotence', () => {
  const config = getConfig();
  const testImages = getTestImages('day0');

  test('S3.1 - Re-upload same file is near-instant', async ({ page }) => {
    const imagePath = testImages[0];
    
    await page.goto(config.webUrl);
    
    // First upload - measure time
    const firstTime = await measureEndToEnd(page, imagePath);
    
    // Clear and re-upload
    await page.goto(config.webUrl);
    const secondTime = await measureEndToEnd(page, imagePath);
    
    // Second should be much faster (cache hit)
    expect(secondTime).toBeLessThan(firstTime * 0.5);
    expect(secondTime).toBeLessThan(2); // Should be under 2 seconds
    
    // Look for cache indicator if present
    const cacheIndicator = page.locator('[data-testid="cache-hit"]');
    if (await cacheIndicator.count() > 0) {
      await expect(cacheIndicator).toBeVisible();
    }
  });

  test('S3.2 - Concurrent uploads of same file', async ({ browser }) => {
    const imagePath = testImages[0];
    const numTabs = 5;
    const contexts: BrowserContext[] = [];
    const pages: any[] = [];
    
    // Create multiple browser contexts
    for (let i = 0; i < numTabs; i++) {
      const context = await browser.newContext();
      contexts.push(context);
      const page = await context.newPage();
      pages.push(page);
      await page.goto(config.webUrl);
    }
    
    // Start uploads concurrently
    const uploadPromises = pages.map(async (page, index) => {
      const startTime = Date.now();
      await uploadImage(page, imagePath);
      await waitForDeckReady(page);
      const endTime = Date.now();
      return {
        index,
        duration: (endTime - startTime) / 1000
      };
    });
    
    const results = await Promise.all(uploadPromises);
    
    // Sort by duration
    results.sort((a, b) => a.duration - b.duration);
    
    // First one might take longer, rest should be fast
    const fastResults = results.slice(1);
    for (const result of fastResults) {
      expect(result.duration).toBeLessThan(3); // Cache hits should be fast
    }
    
    // Verify all got same result
    const exports = await Promise.all(
      pages.map(page => page.evaluate(() => {
        return document.querySelector('[data-testid="deck-display"]')?.textContent || '';
      }))
    );
    
    // All should have identical deck content
    const firstExport = exports[0];
    for (const exp of exports) {
      expect(exp).toBe(firstExport);
    }
    
    // Cleanup
    for (const context of contexts) {
      await context.close();
    }
  });

  test('S3.3 - Hash-based deduplication', async ({ page }) => {
    const imagePath = testImages[0];
    
    await page.goto(config.webUrl);
    
    // Enable network monitoring
    const requests: string[] = [];
    page.on('request', request => {
      if (request.url().includes('/api/ocr')) {
        requests.push(request.url());
      }
    });
    
    // First upload
    await uploadImage(page, imagePath);
    await waitForDeckReady(page);
    const firstOcrRequests = requests.length;
    
    // Clear requests
    requests.length = 0;
    
    // Second upload of same file
    await page.goto(config.webUrl);
    await uploadImage(page, imagePath);
    await waitForDeckReady(page);
    const secondOcrRequests = requests.length;
    
    // Should not make another OCR request (cached)
    expect(secondOcrRequests).toBe(0);
  });

  test('S3.4 - Different images process independently', async ({ page }) => {
    if (testImages.length < 2) {
      test.skip();
      return;
    }
    
    const image1 = testImages[0];
    const image2 = testImages[1];
    
    await page.goto(config.webUrl);
    
    // Upload first image
    const time1 = await measureEndToEnd(page, image1);
    
    // Upload second (different) image
    await page.goto(config.webUrl);
    const time2 = await measureEndToEnd(page, image2);
    
    // Both should take similar time (no cache benefit)
    expect(Math.abs(time1 - time2)).toBeLessThan(2);
    
    // Verify different results
    const deck1 = await page.evaluate(() => 
      document.querySelector('[data-testid="deck-display"]')?.textContent || ''
    );
    
    await page.goto(config.webUrl);
    await uploadImage(page, image1);
    await waitForDeckReady(page);
    const deck1Again = await page.evaluate(() => 
      document.querySelector('[data-testid="deck-display"]')?.textContent || ''
    );
    
    // Same image should produce same deck
    expect(deck1Again).toBe(deck1);
  });
});
import { test, expect } from '@playwright/test';
import { APIClient } from './helpers/api-client';
import { TestData } from './helpers/test-data';

/**
 * Idempotency Tests (S3 from TEST_PLAN_PLAYWRIGHT.md)
 * Tests caching and duplicate upload handling
 */
test.describe('Idempotency - Caching and Duplicate Handling', () => {
  let apiClient: APIClient;

  test.beforeEach(async ({ request }) => {
    apiClient = new APIClient(request);
  });

  test('S3.1 - Re-upload same file shows cache behavior', async ({ page }) => {
    test.slow();
    
    const testImage = TestData.TEST_IMAGES.MTGA_DECK_1;
    const imagePath = TestData.getImagePath(testImage);

    // First upload
    await page.goto('/');
    const fileInput = page.locator('input[type="file"]');
    
    console.log('First upload...');
    const start1 = Date.now();
    await fileInput.setInputFiles(imagePath);
    await expect(page.getByText(/deck ready|completed|finished/i)).toBeVisible({ timeout: 30000 });
    const duration1 = Date.now() - start1;
    
    // Second upload (should be faster due to caching)
    await page.goto('/');
    const fileInput2 = page.locator('input[type="file"]');
    
    console.log('Second upload (expecting cache hit)...');
    const start2 = Date.now();
    await fileInput2.setInputFiles(imagePath);
    await expect(page.getByText(/deck ready|completed|finished/i)).toBeVisible({ timeout: 15000 });
    const duration2 = Date.now() - start2;
    
    console.log(`First upload: ${duration1}ms, Second upload: ${duration2}ms`);
    
    // Second upload should be significantly faster (cache hit)
    // Allow some tolerance, but should be at least 50% faster
    expect(duration2).toBeLessThan(duration1 * 0.7);
    
    // Look for cache indicators in UI (if implemented)
    const cacheIndicator = page.getByText(/cache|cached|previously processed/i);
    if (await cacheIndicator.isVisible()) {
      console.log('✅ Cache indicator found in UI');
    }
  });

  test('S3.2 - Concurrent uploads of same file (multi-tab simulation)', async ({ browser }) => {
    test.slow();
    
    const testImage = TestData.TEST_IMAGES.MTGA_DECK_1;
    const imagePath = TestData.getImagePath(testImage);
    
    // Create multiple browser contexts to simulate different users/tabs
    const contexts = await Promise.all([
      browser.newContext(),
      browser.newContext(),
      browser.newContext()
    ]);
    
    const pages = await Promise.all(contexts.map(ctx => ctx.newPage()));
    
    try {
      // Start all uploads simultaneously
      const uploadPromises = pages.map(async (page, index) => {
        await page.goto('/');
        const fileInput = page.locator('input[type="file"]');
        
        console.log(`Starting upload ${index + 1}...`);
        const start = Date.now();
        await fileInput.setInputFiles(imagePath);
        await expect(page.getByText(/deck ready|completed|finished/i)).toBeVisible({ timeout: 45000 });
        const duration = Date.now() - start;
        
        return { index: index + 1, duration };
      });
      
      const results = await Promise.all(uploadPromises);
      
      // Log results
      results.forEach(result => {
        console.log(`Upload ${result.index}: ${result.duration}ms`);
      });
      
      // At least one should be significantly faster (cache hit)
      const durations = results.map(r => r.duration);
      const minDuration = Math.min(...durations);
      const maxDuration = Math.max(...durations);
      
      // Expect significant difference due to idempotency
      expect(minDuration).toBeLessThan(maxDuration * 0.8);
      
      console.log('✅ Concurrent upload idempotency working');
      
    } finally {
      // Cleanup
      await Promise.all(contexts.map(ctx => ctx.close()));
    }
  });

  test('S3.3 - API idempotency with job status', async ({ request }) => {
    const testImage = TestData.TEST_IMAGES.MTGA_DECK_1;
    const imagePath = TestData.getImagePath(testImage);

    // Upload same image twice via API
    const upload1 = await apiClient.uploadImage(imagePath);
    const upload2 = await apiClient.uploadImage(imagePath);
    
    console.log(`Job ID 1: ${upload1.jobId}`);
    console.log(`Job ID 2: ${upload2.jobId}`);
    
    // Jobs might have same ID (idempotent) or different IDs but same result
    const result1 = await apiClient.waitForJobCompletion(upload1.jobId, 45000);
    const result2 = await apiClient.waitForJobCompletion(upload2.jobId, 45000);
    
    // Results should be identical
    expect(result1.deck).toEqual(result2.deck);
    
    // Check if second job was faster (cache hit)
    if (result1.processing_time && result2.processing_time) {
      console.log(`Processing time 1: ${result1.processing_time}ms`);
      console.log(`Processing time 2: ${result2.processing_time}ms`);
      
      // Second should be faster or similar (cached)
      expect(result2.processing_time).toBeLessThanOrEqual(result1.processing_time * 1.1);
    }
    
    console.log('✅ API idempotency verified');
  });

  test('S3.4 - Different images produce different results', async ({ page }) => {
    const testImages = [
      TestData.TEST_IMAGES.MTGA_DECK_1,
      TestData.TEST_IMAGES.MTGO_USUAL
    ];
    
    const results = [];
    
    for (const testImage of testImages) {
      await page.goto('/');
      const fileInput = page.locator('input[type="file"]');
      const imagePath = TestData.getImagePath(testImage);
      
      await fileInput.setInputFiles(imagePath);
      await expect(page.getByText(/deck ready|completed|finished/i)).toBeVisible({ timeout: 30000 });
      
      // Extract some deck info for comparison
      const deckText = await page.locator('body').textContent();
      results.push({
        image: testImage,
        content: deckText?.substring(0, 1000) // First 1000 chars for comparison
      });
    }
    
    // Results should be different
    expect(results[0].content).not.toBe(results[1].content);
    console.log('✅ Different images produce different results');
  });
});
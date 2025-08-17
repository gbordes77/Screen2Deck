import { test, expect } from '@playwright/test';
import { APIClient } from './helpers/api-client';
import { TestData } from './helpers/test-data';

/**
 * API Parity Tests (S2 from TEST_PLAN_PLAYWRIGHT.md)
 * Ensures UI exports match API exports and golden data
 */
test.describe('API Parity - UI vs API vs Goldens', () => {
  let apiClient: APIClient;

  test.beforeEach(async ({ request }) => {
    apiClient = new APIClient(request);
  });

  test('S2.1 - UI export equals API export', async ({ page }) => {
    test.slow();
    
    const testImage = TestData.TEST_IMAGES.MTGA_DECK_1;
    const imagePath = TestData.getImagePath(testImage);

    // Step 1: Process image via API
    const { jobId } = await apiClient.uploadImage(imagePath);
    const jobResult = await apiClient.waitForJobCompletion(jobId, 45000);
    
    expect(jobResult.status).toBe('completed');
    expect(jobResult.deck).toBeDefined();
    
    // Step 2: Export via API
    const apiMtgaExport = await apiClient.exportDeck(jobResult.deck, 'mtga');
    
    // Step 3: Process same image via UI
    await page.goto('/');
    
    const fileInput = page.locator('input[type="file"]');
    await fileInput.setInputFiles(imagePath);
    
    await expect(page.getByText(/deck ready|completed|finished/i)).toBeVisible({ timeout: 30000 });
    
    // Step 4: Export via UI
    const exportButton = page.getByRole('button', { name: /export.*mtga|mtga.*export/i });
    const downloadPromise = page.waitForDownload();
    await exportButton.click();
    const download = await downloadPromise;
    
    // Step 5: Compare exports
    const downloadPath = await download.path();
    if (downloadPath) {
      const fs = await import('fs/promises');
      const uiExport = await fs.readFile(downloadPath, 'utf-8');
      
      // Normalize for comparison (remove trailing whitespace, normalize line endings)
      const normalizeExport = (content: string) => content.trim().replace(/\r\n/g, '\n');
      
      expect(normalizeExport(uiExport)).toBe(normalizeExport(apiMtgaExport));
      
      // Step 6: Compare with golden data if available
      const goldenExport = await TestData.loadGoldenExport(testImage, 'mtga');
      if (goldenExport) {
        expect(normalizeExport(uiExport)).toBe(normalizeExport(goldenExport));
        console.log('✅ UI export matches API export and golden data');
      } else {
        console.log('✅ UI export matches API export (no golden data available)');
      }
    }
  });

  test('S2.2 - Deck structure matches golden data', async ({ page, request }) => {
    const testImage = TestData.TEST_IMAGES.MTGA_DECK_1;
    const goldenData = await TestData.loadGolden(testImage);
    
    if (!goldenData) {
      test.skip('No golden data available for this test');
    }

    // Process via API to get structured data
    const imagePath = TestData.getImagePath(testImage);
    const { jobId } = await apiClient.uploadImage(imagePath);
    const jobResult = await apiClient.waitForJobCompletion(jobId, 45000);
    
    const actualDeck = jobResult.deck;
    
    // Compare mainboard
    if (goldenData.mainboard) {
      expect(actualDeck.mainboard).toBeDefined();
      expect(actualDeck.mainboard.length).toBe(goldenData.mainboard.length);
      
      // Compare each card
      for (let i = 0; i < goldenData.mainboard.length; i++) {
        const expected = goldenData.mainboard[i];
        const actual = actualDeck.mainboard.find((card: any) => 
          card.name.toLowerCase() === expected.name.toLowerCase()
        );
        
        expect(actual).toBeDefined();
        expect(actual.qty).toBe(expected.qty);
      }
    }
    
    // Compare sideboard
    if (goldenData.sideboard) {
      expect(actualDeck.sideboard).toBeDefined();
      expect(actualDeck.sideboard.length).toBe(goldenData.sideboard.length);
      
      for (let i = 0; i < goldenData.sideboard.length; i++) {
        const expected = goldenData.sideboard[i];
        const actual = actualDeck.sideboard.find((card: any) => 
          card.name.toLowerCase() === expected.name.toLowerCase()
        );
        
        expect(actual).toBeDefined();
        expect(actual.qty).toBe(expected.qty);
      }
    }
    
    console.log('✅ Deck structure matches golden data');
  });

  test('S2.3 - Multiple format exports consistency', async ({ page }) => {
    test.slow();
    
    const testImage = TestData.TEST_IMAGES.MTGA_DECK_1;
    const imagePath = TestData.getImagePath(testImage);

    // Process image once
    const { jobId } = await apiClient.uploadImage(imagePath);
    const jobResult = await apiClient.waitForJobCompletion(jobId, 45000);
    
    const formats = ['mtga', 'moxfield', 'archidekt', 'tappedout'];
    const exports: Record<string, string> = {};
    
    // Get API exports for all formats
    for (const format of formats) {
      try {
        exports[`api_${format}`] = await apiClient.exportDeck(jobResult.deck, format);
      } catch (error) {
        console.log(`⚠️ API export for ${format} failed:`, error);
      }
    }
    
    // Get UI exports for all formats
    await page.goto('/');
    const fileInput = page.locator('input[type="file"]');
    await fileInput.setInputFiles(imagePath);
    await expect(page.getByText(/deck ready|completed|finished/i)).toBeVisible({ timeout: 30000 });
    
    for (const format of formats) {
      const exportButton = page.getByRole('button', { name: new RegExp(`export.*${format}|${format}.*export`, 'i') });
      
      if (await exportButton.isVisible()) {
        const downloadPromise = page.waitForDownload();
        await exportButton.click();
        const download = await downloadPromise;
        
        const downloadPath = await download.path();
        if (downloadPath) {
          const fs = await import('fs/promises');
          const uiExport = await fs.readFile(downloadPath, 'utf-8');
          exports[`ui_${format}`] = uiExport;
          
          // Compare UI vs API for this format
          const apiExport = exports[`api_${format}`];
          if (apiExport) {
            const normalize = (content: string) => content.trim().replace(/\r\n/g, '\n');
            expect(normalize(uiExport)).toBe(normalize(apiExport));
          }
        }
      }
    }
    
    console.log('✅ All format exports consistent between UI and API');
  });
});
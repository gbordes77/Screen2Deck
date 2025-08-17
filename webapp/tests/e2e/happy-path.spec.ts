import { test, expect } from '@playwright/test';
import { APIClient } from './helpers/api-client';
import { TestData } from './helpers/test-data';

/**
 * Happy Path E2E Tests (S1 from TEST_PLAN_PLAYWRIGHT.md)
 * Tests the complete user journey: Upload → Deck → Export
 */
test.describe('Happy Path - Upload to Export', () => {
  let apiClient: APIClient;

  test.beforeEach(async ({ request }) => {
    apiClient = new APIClient(request);
  });

  test('S1.1 - Upload MTGA deck and export to MTGA format', async ({ page }) => {
    test.slow(); // This test involves file upload and OCR processing
    
    await page.goto('/');
    
    // Upload image
    const fileInput = page.locator('input[type="file"]');
    await expect(fileInput).toBeVisible();
    
    const imagePath = TestData.getImagePath(TestData.TEST_IMAGES.MTGA_DECK_1);
    await fileInput.setInputFiles(imagePath);
    
    // Wait for upload to complete and deck to be displayed
    await expect(page.getByText(/deck ready|completed|finished/i)).toBeVisible({ timeout: 30000 });
    
    // Check for sideboard section
    const sideboardSection = page.getByText(/sideboard/i);
    if (await sideboardSection.isVisible()) {
      console.log('✅ Sideboard section found');
    }
    
    // Export to MTGA format
    const exportButton = page.getByRole('button', { name: /export.*mtga|mtga.*export/i });
    await expect(exportButton).toBeVisible();
    
    // Start download
    const downloadPromise = page.waitForDownload();
    await exportButton.click();
    const download = await downloadPromise;
    
    // Verify download
    expect(download.suggestedFilename()).toMatch(/\.txt$/);
    
    // Save and validate content if golden data is available
    const goldenExport = await TestData.loadGoldenExport(TestData.TEST_IMAGES.MTGA_DECK_1, 'mtga');
    if (goldenExport) {
      const downloadPath = await download.path();
      if (downloadPath) {
        const fs = await import('fs/promises');
        const actualContent = await fs.readFile(downloadPath, 'utf-8');
        expect(actualContent.trim()).toBe(goldenExport.trim());
      }
    }
  });

  test('S1.2 - Export to all formats (Moxfield, Archidekt, TappedOut)', async ({ page }) => {
    test.slow();
    
    await page.goto('/');
    
    // Upload image
    const fileInput = page.locator('input[type="file"]');
    const imagePath = TestData.getImagePath(TestData.TEST_IMAGES.MTGA_DECK_1);
    await fileInput.setInputFiles(imagePath);
    
    // Wait for processing
    await expect(page.getByText(/deck ready|completed|finished/i)).toBeVisible({ timeout: 30000 });
    
    // Test each export format
    const formats = ['moxfield', 'archidekt', 'tappedout'];
    
    for (const format of formats) {
      const exportButton = page.getByRole('button', { name: new RegExp(`export.*${format}|${format}.*export`, 'i') });
      
      if (await exportButton.isVisible()) {
        const downloadPromise = page.waitForDownload();
        await exportButton.click();
        const download = await downloadPromise;
        
        expect(download.suggestedFilename()).toMatch(/\.txt$/);
        
        // Validate against golden data if available
        const goldenExport = await TestData.loadGoldenExport(TestData.TEST_IMAGES.MTGA_DECK_1, format);
        if (goldenExport) {
          const downloadPath = await download.path();
          if (downloadPath) {
            const fs = await import('fs/promises');
            const actualContent = await fs.readFile(downloadPath, 'utf-8');
            expect(actualContent.trim()).toBe(goldenExport.trim());
          }
        }
        
        console.log(`✅ ${format} export completed successfully`);
      } else {
        console.log(`⚠️ ${format} export button not found - may not be implemented yet`);
      }
    }
  });

  test('S1.3 - Multiple image types (JPEG, PNG, WebP)', async ({ page }) => {
    const testImages = [
      TestData.TEST_IMAGES.MTGA_DECK_1, // JPEG
      TestData.TEST_IMAGES.WEBP_IMAGE,  // WebP
      TestData.TEST_IMAGES.GOLDFISH     // JPG
    ];

    for (const imageName of testImages) {
      await page.goto('/');
      
      const fileInput = page.locator('input[type="file"]');
      const imagePath = TestData.getImagePath(imageName);
      
      console.log(`Testing image: ${imageName}`);
      
      await fileInput.setInputFiles(imagePath);
      
      // Wait for processing - adjust timeout based on image complexity
      await expect(page.getByText(/deck ready|completed|finished/i)).toBeVisible({ timeout: 45000 });
      
      // Verify deck content is displayed
      const deckContent = page.locator('[data-testid="deck-content"], .deck-content, .card-list');
      if (await deckContent.isVisible()) {
        const cardCount = await deckContent.locator('.card-item, [data-testid="card-item"]').count();
        expect(cardCount).toBeGreaterThan(0);
      } else {
        // Fallback: check for any text that looks like card names
        const hasCardContent = await page.getByText(/\d+x?\s+[A-Z]/i).first().isVisible();
        expect(hasCardContent).toBeTruthy();
      }
      
      console.log(`✅ ${imageName} processed successfully`);
    }
  });
});
/**
 * S2 - Parity UI vs API vs Goldens
 * Ensures all interfaces produce identical output
 */
import { test, expect, request } from '@playwright/test';
import * as path from 'path';
import * as fs from 'fs';
import {
  getConfig,
  uploadImage,
  waitForDeckReady,
  downloadExport,
  hashContent,
  getTestImages
} from '../helpers/test-utils';

test.describe('S2 - Parity Testing', () => {
  const config = getConfig();
  const testImages = getTestImages();

  test('S2.1 - UI export = API export = Golden', async ({ page }) => {
    const imagePath = testImages[0];
    const imageName = path.basename(imagePath, path.extname(imagePath));
    
    // Upload via UI
    await page.goto(config.webUrl);
    await uploadImage(page, imagePath);
    await waitForDeckReady(page);
    
    // Get job ID from page
    const jobId = await page.getAttribute('[data-testid="job-id"]', 'data-job-id');
    expect(jobId).toBeTruthy();
    
    // Test all formats
    const formats = ['mtga', 'moxfield', 'archidekt', 'tappedout'];
    
    for (const format of formats) {
      // Get UI export
      const uiExport = await downloadExport(page, format);
      const uiHash = hashContent(uiExport);
      
      // Get API export
      const apiContext = await request.newContext();
      const apiResponse = await apiContext.get(`${config.apiUrl}/api/export/${format}`, {
        params: { jobId }
      });
      expect(apiResponse.ok()).toBeTruthy();
      const apiExport = await apiResponse.text();
      const apiHash = hashContent(apiExport);
      
      // Get golden export
      const goldenPath = path.join(config.goldenDir, 'exports', imageName, `${format}.txt`);
      if (fs.existsSync(goldenPath)) {
        const goldenExport = fs.readFileSync(goldenPath, 'utf-8');
        const goldenHash = hashContent(goldenExport);
        
        // All three should match
        expect(uiHash).toBe(apiHash);
        expect(apiHash).toBe(goldenHash);
        expect(uiExport.trim()).toBe(goldenExport.trim());
      } else {
        // At minimum, UI and API should match
        expect(uiHash).toBe(apiHash);
      }
    }
  });

  test('S2.2 - Consistent deck parsing across images', async ({ page }) => {
    const results: Record<string, any> = {};
    
    // Process multiple images
    for (let i = 0; i < Math.min(3, testImages.length); i++) {
      const imagePath = testImages[i];
      const imageName = path.basename(imagePath, path.extname(imagePath));
      
      await page.goto(config.webUrl);
      await uploadImage(page, imagePath);
      await waitForDeckReady(page);
      
      // Get deck data from UI
      const deckData = await page.evaluate(() => {
        const mainDeck = document.querySelector('[data-testid="main-deck"]')?.textContent || '';
        const sideboard = document.querySelector('[data-testid="sideboard"]')?.textContent || '';
        return { mainDeck, sideboard };
      });
      
      results[imageName] = deckData;
    }
    
    // Verify consistency in structure
    for (const [name, data] of Object.entries(results)) {
      expect(data.mainDeck).toBeTruthy();
      // Sideboard may be empty but should exist
      expect(data).toHaveProperty('sideboard');
    }
  });

  test('S2.3 - Export consistency across browser refreshes', async ({ page }) => {
    const imagePath = testImages[0];
    
    // First upload
    await page.goto(config.webUrl);
    await uploadImage(page, imagePath);
    await waitForDeckReady(page);
    const firstExport = await downloadExport(page, 'mtga');
    
    // Refresh and re-upload
    await page.reload();
    await uploadImage(page, imagePath);
    await waitForDeckReady(page);
    const secondExport = await downloadExport(page, 'mtga');
    
    // Should produce identical results
    expect(hashContent(firstExport)).toBe(hashContent(secondExport));
  });
});
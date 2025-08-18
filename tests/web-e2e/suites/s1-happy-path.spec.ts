/**
 * S1 - Happy Path UI Tests
 * Upload → Deck → Export for all formats
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

test.describe('S1 - Happy Path', () => {
  const config = getConfig();
  const testImages = getTestImages(); // defaults to 'images'

  test.beforeEach(async ({ page }) => {
    await page.goto(config.webUrl);
    await expect(page).toHaveTitle(/MTG Deck Scanner/);
  });

  test('S1.1 - Upload → Deck → Export MTGA', async ({ page }) => {
    const imagePath = testImages[0];
    const imageName = path.basename(imagePath, path.extname(imagePath));
    
    // Upload image
    await uploadImage(page, imagePath);
    
    // Wait for deck to be ready
    await waitForDeckReady(page);
    
    // Verify deck is displayed
    await expect(page.locator('[data-testid="deck-display"]')).toBeVisible();
    await expect(page.locator('text=Sideboard')).toBeVisible();
    
    // Download MTGA export
    const mtgaContent = await downloadExport(page, 'mtga');
    
    // Compare with golden
    const goldenPath = path.join(config.goldenDir, 'exports', imageName, 'mtga.txt');
    if (fs.existsSync(goldenPath)) {
      expect(compareWithGolden(mtgaContent, goldenPath)).toBe(true);
    }
    
    // Verify format structure
    expect(mtgaContent).toContain('Deck');
    expect(mtgaContent).toContain('Sideboard');
  });

  test('S1.2 - Export Moxfield / Archidekt / TappedOut', async ({ page }) => {
    const imagePath = testImages[0];
    const imageName = path.basename(imagePath, path.extname(imagePath));
    
    await uploadImage(page, imagePath);
    await waitForDeckReady(page);
    
    // Test all export formats
    const formats = ['moxfield', 'archidekt', 'tappedout'];
    
    for (const format of formats) {
      const content = await downloadExport(page, format);
      const goldenPath = path.join(config.goldenDir, 'exports', imageName, `${format}.txt`);
      
      if (fs.existsSync(goldenPath)) {
        expect(compareWithGolden(content, goldenPath)).toBe(true);
      }
      
      // Format-specific validations
      switch (format) {
        case 'moxfield':
          expect(content).toMatch(/SB:/);
          break;
        case 'archidekt':
          expect(content).toMatch(/\dx/);
          expect(content).toContain('Sideboard:');
          break;
        case 'tappedout':
          expect(content).toContain('Sideboard');
          break;
      }
    }
  });

  test('S1.3 - Multiple images in sequence', async ({ page }) => {
    // Test with first 3 images
    for (let i = 0; i < Math.min(3, testImages.length); i++) {
      const imagePath = testImages[i];
      
      // Navigate fresh for each test
      await page.goto(config.webUrl);
      await uploadImage(page, imagePath);
      await waitForDeckReady(page);
      
      // Verify each produces a valid deck
      await expect(page.locator('[data-testid="deck-display"]')).toBeVisible();
      
      // Export and verify at least one format
      const mtgaContent = await downloadExport(page, 'mtga');
      expect(mtgaContent).toBeTruthy();
      expect(mtgaContent.length).toBeGreaterThan(10);
    }
  });
});
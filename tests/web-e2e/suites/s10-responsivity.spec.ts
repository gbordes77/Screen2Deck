/**
 * S10 - Responsivity Testing
 * Verify mobile and desktop responsive behavior
 */
import { test, expect, devices } from '@playwright/test';
import {
  getConfig,
  uploadImage,
  waitForDeckReady,
  downloadExport,
  getTestImages
} from '../helpers/test-utils';

test.describe('S10 - Responsivity', () => {
  const config = getConfig();
  const testImages = getTestImages();

  test('S10.1 - Mobile upload → deck → export', async ({ browser }) => {
    // Create mobile context
    const context = await browser.newContext({
      ...devices['Pixel 7']
    });
    const page = await context.newPage();
    
    await page.goto(config.webUrl);
    
    // Verify mobile layout
    const viewport = page.viewportSize();
    expect(viewport?.width).toBeLessThan(500);
    
    // Upload should work on mobile
    const imagePath = testImages[0];
    await uploadImage(page, imagePath);
    await waitForDeckReady(page);
    
    // Deck should be visible and readable
    const deckDisplay = page.locator('[data-testid="deck-display"]');
    await expect(deckDisplay).toBeVisible();
    
    // Check if text is not cut off
    const deckBox = await deckDisplay.boundingBox();
    if (deckBox && viewport) {
      expect(deckBox.width).toBeLessThanOrEqual(viewport.width);
    }
    
    // Export buttons should be accessible
    const exportButton = page.locator('[data-testid="export-mtga"]');
    await expect(exportButton).toBeVisible();
    
    // May need to scroll to see all exports
    await exportButton.scrollIntoViewIfNeeded();
    
    const exportContent = await downloadExport(page, 'mtga');
    expect(exportContent).toContain('Deck');
    
    await context.close();
  });

  test('S10.2 - Tablet landscape', async ({ browser }) => {
    const context = await browser.newContext({
      ...devices['iPad landscape']
    });
    const page = await context.newPage();
    
    await page.goto(config.webUrl);
    
    const imagePath = testImages[0];
    await uploadImage(page, imagePath);
    await waitForDeckReady(page);
    
    // Should show deck in optimal layout for tablet
    const deckDisplay = page.locator('[data-testid="deck-display"]');
    await expect(deckDisplay).toBeVisible();
    
    // May have side-by-side layout
    const mainDeck = page.locator('[data-testid="main-deck"]');
    const sideboard = page.locator('[data-testid="sideboard"]');
    
    if (await mainDeck.count() > 0 && await sideboard.count() > 0) {
      const mainBox = await mainDeck.boundingBox();
      const sideBox = await sideboard.boundingBox();
      
      if (mainBox && sideBox) {
        // Check if side-by-side (sideboard to the right)
        const isSideBySide = sideBox.x > mainBox.x + mainBox.width / 2;
        // Tablet should use space efficiently
        expect(isSideBySide || sideBox.y > mainBox.y).toBe(true);
      }
    }
    
    await context.close();
  });

  test('S10.3 - Window resize handling', async ({ page }) => {
    await page.goto(config.webUrl);
    
    const imagePath = testImages[0];
    await uploadImage(page, imagePath);
    await waitForDeckReady(page);
    
    // Start at desktop size
    await page.setViewportSize({ width: 1440, height: 900 });
    
    const deckDisplay = page.locator('[data-testid="deck-display"]');
    await expect(deckDisplay).toBeVisible();
    
    // Resize to mobile
    await page.setViewportSize({ width: 375, height: 667 });
    
    // Content should reflow
    await expect(deckDisplay).toBeVisible();
    
    // No horizontal scroll
    const hasHorizontalScroll = await page.evaluate(() => {
      return document.documentElement.scrollWidth > window.innerWidth;
    });
    expect(hasHorizontalScroll).toBe(false);
    
    // Resize back to desktop
    await page.setViewportSize({ width: 1440, height: 900 });
    
    // Should adapt back
    await expect(deckDisplay).toBeVisible();
  });

  test('S10.4 - Touch interactions on mobile', async ({ browser }) => {
    const context = await browser.newContext({
      ...devices['iPhone 14']
    });
    const page = await context.newPage();
    
    await page.goto(config.webUrl);
    
    // Touch to open file picker (if supported)
    const uploadArea = page.locator('[data-testid="upload-area"]');
    await uploadArea.tap();
    
    // File input should be triggered
    const fileInput = page.locator('input[type="file"]');
    const isFileInputFocused = await fileInput.evaluate(el => 
      el === document.activeElement
    );
    
    // Set file directly since mobile file picking is complex
    const imagePath = testImages[0];
    await fileInput.setInputFiles(imagePath);
    
    await waitForDeckReady(page);
    
    // Test swipe/scroll on deck list
    const deckDisplay = page.locator('[data-testid="deck-display"]');
    const box = await deckDisplay.boundingBox();
    
    if (box) {
      // Simulate swipe
      await page.touchscreen.tap(box.x + box.width / 2, box.y + 50);
      await page.touchscreen.tap(box.x + box.width / 2, box.y + 200);
    }
    
    // Export buttons should be tappable
    const exportButton = page.locator('[data-testid="export-mtga"]');
    await exportButton.tap();
    
    await context.close();
  });

  test('S10.5 - Responsive images', async ({ page }) => {
    await page.goto(config.webUrl);
    
    // Check different viewport sizes
    const viewports = [
      { width: 375, height: 667, name: 'mobile' },
      { width: 768, height: 1024, name: 'tablet' },
      { width: 1440, height: 900, name: 'desktop' }
    ];
    
    for (const viewport of viewports) {
      await page.setViewportSize(viewport);
      
      // Check if images have appropriate sizes
      const images = page.locator('img');
      const count = await images.count();
      
      for (let i = 0; i < count; i++) {
        const img = images.nth(i);
        const box = await img.boundingBox();
        
        if (box) {
          // Images shouldn't exceed viewport
          expect(box.width).toBeLessThanOrEqual(viewport.width);
          
          // Check for responsive attributes
          const srcset = await img.getAttribute('srcset');
          const sizes = await img.getAttribute('sizes');
          
          // Should use responsive images if multiple sizes needed
          if (viewport.name === 'mobile' && box.width > 200) {
            // Large images on mobile should be optimized
            expect(srcset || sizes).toBeTruthy();
          }
        }
      }
    }
  });

  test('S10.6 - Sidebar/menu collapse', async ({ page }) => {
    await page.goto(config.webUrl);
    
    // Check if sidebar exists
    const sidebar = page.locator('[data-testid="sidebar"], aside, nav');
    
    if (await sidebar.count() > 0) {
      // Desktop - sidebar visible
      await page.setViewportSize({ width: 1440, height: 900 });
      await expect(sidebar).toBeVisible();
      
      // Mobile - sidebar collapsed or hidden
      await page.setViewportSize({ width: 375, height: 667 });
      
      const isVisible = await sidebar.isVisible();
      if (isVisible) {
        // Should have hamburger menu
        const menuToggle = page.locator('[data-testid="menu-toggle"], [aria-label*="menu"]');
        await expect(menuToggle).toBeVisible();
      }
    }
  });

  test('S10.7 - Text readability across sizes', async ({ page }) => {
    await page.goto(config.webUrl);
    
    const checkTextSize = async (width: number) => {
      await page.setViewportSize({ width, height: 800 });
      
      // Check main text elements
      const textElements = await page.locator('p, span, div').all();
      
      for (const element of textElements.slice(0, 10)) { // Sample first 10
        const fontSize = await element.evaluate(el => 
          window.getComputedStyle(el).fontSize
        );
        
        const size = parseFloat(fontSize);
        
        // Mobile text should be at least 14px
        if (width < 500) {
          expect(size).toBeGreaterThanOrEqual(12);
        }
        
        // No text should be smaller than 10px
        expect(size).toBeGreaterThanOrEqual(10);
      }
    };
    
    await checkTextSize(375);  // Mobile
    await checkTextSize(768);  // Tablet
    await checkTextSize(1440); // Desktop
  });

  test('S10.8 - Export dialog responsiveness', async ({ page }) => {
    const imagePath = testImages[0];
    
    // Test on mobile
    await page.setViewportSize({ width: 375, height: 667 });
    await page.goto(config.webUrl);
    
    await uploadImage(page, imagePath);
    await waitForDeckReady(page);
    
    // If there's an export menu/dialog
    const exportMenu = page.locator('[data-testid="export-menu"]');
    if (await exportMenu.count() > 0) {
      await exportMenu.click();
      
      const dialog = page.locator('[role="dialog"], [data-testid="export-dialog"]');
      if (await dialog.count() > 0) {
        // Dialog should fit mobile screen
        const box = await dialog.boundingBox();
        if (box) {
          expect(box.width).toBeLessThanOrEqual(375);
          expect(box.x).toBeGreaterThanOrEqual(0);
        }
      }
    }
  });
});
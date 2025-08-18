/**
 * S11 - Visual Regression Testing
 * Screenshot comparison for UI consistency
 */
import { test, expect } from '@playwright/test';
import * as path from 'path';
import * as fs from 'fs';
import {
  getConfig,
  uploadImage,
  waitForDeckReady,
  getTestImages
} from '../helpers/test-utils';

test.describe('S11 - Visual Regression', () => {
  const config = getConfig();
  const testImages = getTestImages();

  test('S11.1 - Deck panel screenshot', async ({ page }) => {
    const imagePath = testImages[0];
    
    await page.goto(config.webUrl);
    await uploadImage(page, imagePath);
    await waitForDeckReady(page);
    
    // Wait for animations to complete
    await page.waitForTimeout(1000);
    
    // Mask dynamic content
    const deckPanel = page.locator('[data-testid="deck-panel"], [data-testid="deck-display"]');
    
    // Take screenshot with masks
    await expect(deckPanel).toHaveScreenshot('deck-panel.png', {
      mask: [
        page.locator('[data-testid="timestamp"]'),
        page.locator('[data-testid="job-id"]'),
        page.locator('.timestamp'),
        page.locator('.job-id')
      ],
      maxDiffPixels: 100,
      threshold: 0.01 // 1% difference threshold
    });
  });

  test('S11.2 - Upload area visual', async ({ page }) => {
    await page.goto(config.webUrl);
    
    const uploadArea = page.locator('[data-testid="upload-area"]');
    
    // Default state
    await expect(uploadArea).toHaveScreenshot('upload-area-default.png', {
      maxDiffPixels: 50
    });
    
    // Hover state
    await uploadArea.hover();
    await page.waitForTimeout(300); // Wait for transition
    
    await expect(uploadArea).toHaveScreenshot('upload-area-hover.png', {
      maxDiffPixels: 50
    });
    
    // Drag over state (if supported)
    await page.evaluate(() => {
      const area = document.querySelector('[data-testid="upload-area"]');
      if (area) {
        const event = new DragEvent('dragover', {
          dataTransfer: new DataTransfer(),
          bubbles: true
        });
        area.dispatchEvent(event);
        area.classList.add('drag-over'); // Force drag state
      }
    });
    
    await expect(uploadArea).toHaveScreenshot('upload-area-dragover.png', {
      maxDiffPixels: 50
    });
  });

  test('S11.3 - Export buttons visual', async ({ page }) => {
    const imagePath = testImages[0];
    
    await page.goto(config.webUrl);
    await uploadImage(page, imagePath);
    await waitForDeckReady(page);
    
    // Screenshot export section
    const exportSection = page.locator('[data-testid="export-section"], .export-buttons');
    
    if (await exportSection.count() > 0) {
      await expect(exportSection).toHaveScreenshot('export-section.png', {
        maxDiffPixels: 100
      });
    } else {
      // Individual buttons
      const formats = ['mtga', 'moxfield', 'archidekt', 'tappedout'];
      
      for (const format of formats) {
        const button = page.locator(`[data-testid="export-${format}"]`);
        if (await button.count() > 0) {
          await expect(button).toHaveScreenshot(`export-button-${format}.png`, {
            maxDiffPixels: 20
          });
        }
      }
    }
  });

  test('S11.4 - Progress indicator visual', async ({ page }) => {
    await page.goto(config.webUrl);
    
    // Mock slow processing to capture progress
    await page.route('**/api/ocr/**', async route => {
      await new Promise(resolve => setTimeout(resolve, 2000));
      route.continue();
    });
    
    const imagePath = testImages[0];
    const fileInput = page.locator('input[type="file"]');
    await fileInput.setInputFiles(imagePath);
    
    // Wait for processing to start
    await page.waitForTimeout(500);
    
    // Capture progress indicator
    const progressIndicator = page.locator('[data-testid="progress"], [data-testid="spinner"], .loading');
    
    if (await progressIndicator.count() > 0) {
      await expect(progressIndicator).toHaveScreenshot('progress-indicator.png', {
        maxDiffPixels: 100,
        animations: 'disabled' // Disable animations for consistency
      });
    }
  });

  test('S11.5 - Error state visual', async ({ page }) => {
    await page.goto(config.webUrl);
    
    // Trigger error
    await page.route('**/api/ocr/**', route => {
      route.fulfill({
        status: 500,
        body: JSON.stringify({ error: 'Server error' })
      });
    });
    
    const imagePath = testImages[0];
    await uploadImage(page, imagePath);
    
    // Wait for error
    await page.waitForTimeout(2000);
    
    const errorDisplay = page.locator('[data-testid="error-message"], [data-testid="error-toast"], .error');
    
    if (await errorDisplay.count() > 0) {
      await expect(errorDisplay.first()).toHaveScreenshot('error-display.png', {
        maxDiffPixels: 50
      });
    }
  });

  test('S11.6 - Dark mode visual', async ({ page }) => {
    // Check if dark mode is supported
    await page.goto(config.webUrl);
    
    // Try to enable dark mode
    const darkModeToggle = page.locator('[data-testid="dark-mode-toggle"], [aria-label*="theme"], [aria-label*="dark"]');
    
    if (await darkModeToggle.count() > 0) {
      await darkModeToggle.click();
      await page.waitForTimeout(500); // Wait for theme transition
      
      // Take screenshots of main areas in dark mode
      const uploadArea = page.locator('[data-testid="upload-area"]');
      await expect(uploadArea).toHaveScreenshot('upload-area-dark.png', {
        maxDiffPixels: 100
      });
      
      // Upload and check deck display in dark mode
      const imagePath = testImages[0];
      await uploadImage(page, imagePath);
      await waitForDeckReady(page);
      
      const deckDisplay = page.locator('[data-testid="deck-display"]');
      await expect(deckDisplay).toHaveScreenshot('deck-display-dark.png', {
        mask: [
          page.locator('[data-testid="timestamp"]'),
          page.locator('[data-testid="job-id"]')
        ],
        maxDiffPixels: 100
      });
    } else {
      // Use color scheme preference
      await page.emulateMedia({ colorScheme: 'dark' });
      await page.reload();
      
      // Check if styles changed
      const bgColor = await page.evaluate(() => 
        window.getComputedStyle(document.body).backgroundColor
      );
      
      if (bgColor !== 'rgb(255, 255, 255)') {
        // Dark mode detected
        await expect(page).toHaveScreenshot('full-page-dark.png', {
          fullPage: true,
          maxDiffPixels: 500
        });
      }
    }
  });

  test('S11.7 - Mobile visual regression', async ({ browser }) => {
    const context = await browser.newContext({
      viewport: { width: 375, height: 667 },
      deviceScaleFactor: 2,
    });
    const page = await context.newPage();
    
    await page.goto(config.webUrl);
    
    // Mobile upload area
    const uploadArea = page.locator('[data-testid="upload-area"]');
    await expect(uploadArea).toHaveScreenshot('upload-area-mobile.png', {
      maxDiffPixels: 50
    });
    
    // Upload and check mobile deck display
    const imagePath = testImages[0];
    await uploadImage(page, imagePath);
    await waitForDeckReady(page);
    
    const deckDisplay = page.locator('[data-testid="deck-display"]');
    await expect(deckDisplay).toHaveScreenshot('deck-display-mobile.png', {
      mask: [
        page.locator('[data-testid="timestamp"]'),
        page.locator('[data-testid="job-id"]')
      ],
      maxDiffPixels: 100
    });
    
    await context.close();
  });

  test('S11.8 - Component states visual', async ({ page }) => {
    await page.goto(config.webUrl);
    
    // Button states
    const button = page.locator('button').first();
    if (await button.count() > 0) {
      // Normal
      await expect(button).toHaveScreenshot('button-normal.png', {
        maxDiffPixels: 20
      });
      
      // Hover
      await button.hover();
      await page.waitForTimeout(200);
      await expect(button).toHaveScreenshot('button-hover.png', {
        maxDiffPixels: 20
      });
      
      // Focus
      await button.focus();
      await expect(button).toHaveScreenshot('button-focus.png', {
        maxDiffPixels: 20
      });
      
      // Active (mousedown)
      await button.dispatchEvent('mousedown');
      await expect(button).toHaveScreenshot('button-active.png', {
        maxDiffPixels: 20
      });
      await button.dispatchEvent('mouseup');
    }
    
    // Input states
    const input = page.locator('input[type="text"], input[type="search"]').first();
    if (await input.count() > 0) {
      // Empty
      await expect(input).toHaveScreenshot('input-empty.png', {
        maxDiffPixels: 20
      });
      
      // Focused
      await input.focus();
      await expect(input).toHaveScreenshot('input-focus.png', {
        maxDiffPixels: 20
      });
      
      // With value
      await input.fill('Test value');
      await expect(input).toHaveScreenshot('input-filled.png', {
        maxDiffPixels: 20
      });
    }
  });
});
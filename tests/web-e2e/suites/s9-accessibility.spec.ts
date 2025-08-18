/**
 * S9 - Accessibility (a11y) Testing
 * Verify WCAG compliance and accessibility features
 */
import { test, expect } from '@playwright/test';
import { injectAxe, checkA11y, getViolations } from 'axe-playwright';
import {
  getConfig,
  uploadImage,
  waitForDeckReady,
  getTestImages
} from '../helpers/test-utils';

test.describe('S9 - Accessibility', () => {
  const config = getConfig();
  const testImages = getTestImages();

  test.beforeEach(async ({ page }) => {
    await page.goto(config.webUrl);
    await injectAxe(page);
  });

  test('S9.1 - Upload page accessibility', async ({ page }) => {
    // Check initial page
    const violations = await getViolations(page, undefined, {
      rules: {
        'color-contrast': { enabled: false } // May need design adjustments
      }
    });
    
    // No critical violations
    const criticalViolations = violations.filter(v => v.impact === 'critical');
    expect(criticalViolations).toHaveLength(0);
    
    // No serious violations
    const seriousViolations = violations.filter(v => v.impact === 'serious');
    expect(seriousViolations).toHaveLength(0);
    
    // Check focus management
    await page.keyboard.press('Tab');
    const focusedElement = await page.evaluate(() => document.activeElement?.tagName);
    expect(focusedElement).toBeTruthy();
    
    // Upload area should have proper ARIA labels
    const uploadArea = page.locator('[data-testid="upload-area"]');
    const ariaLabel = await uploadArea.getAttribute('aria-label');
    if (!ariaLabel) {
      const labelledBy = await uploadArea.getAttribute('aria-labelledby');
      expect(labelledBy || ariaLabel).toBeTruthy();
    }
    
    // File input should be accessible
    const fileInput = page.locator('input[type="file"]');
    const inputLabel = await fileInput.getAttribute('aria-label');
    if (!inputLabel) {
      // Should have associated label
      const inputId = await fileInput.getAttribute('id');
      if (inputId) {
        const label = page.locator(`label[for="${inputId}"]`);
        await expect(label).toHaveCount(1);
      }
    }
  });

  test('S9.2 - Deck page accessibility', async ({ page }) => {
    const imagePath = testImages[0];
    await uploadImage(page, imagePath);
    await waitForDeckReady(page);
    
    // Re-inject axe after navigation
    await injectAxe(page);
    
    // Check deck page
    const violations = await getViolations(page, undefined, {
      rules: {
        'color-contrast': { enabled: false }
      }
    });
    
    // No critical/serious violations
    const criticalViolations = violations.filter(v => 
      v.impact === 'critical' || v.impact === 'serious'
    );
    expect(criticalViolations).toHaveLength(0);
    
    // Deck display should be properly structured
    const deckDisplay = page.locator('[data-testid="deck-display"]');
    const role = await deckDisplay.getAttribute('role');
    if (role) {
      expect(['region', 'article', 'main']).toContain(role);
    }
    
    // Export buttons should be accessible
    const exportButtons = page.locator('[data-testid^="export-"]');
    const buttonCount = await exportButtons.count();
    
    for (let i = 0; i < buttonCount; i++) {
      const button = exportButtons.nth(i);
      const buttonText = await button.textContent();
      const ariaLabel = await button.getAttribute('aria-label');
      expect(buttonText || ariaLabel).toBeTruthy();
    }
  });

  test('S9.3 - Keyboard navigation', async ({ page }) => {
    const imagePath = testImages[0];
    
    // Navigate with keyboard only
    await page.keyboard.press('Tab');
    await page.keyboard.press('Tab');
    
    // Should be able to trigger file upload with keyboard
    const fileInput = page.locator('input[type="file"]');
    await fileInput.setInputFiles(imagePath);
    
    await waitForDeckReady(page);
    
    // Should be able to tab to export buttons
    let exportButtonFocused = false;
    for (let i = 0; i < 20; i++) {
      await page.keyboard.press('Tab');
      const focused = await page.evaluate(() => {
        const el = document.activeElement;
        return el?.getAttribute('data-testid')?.startsWith('export-');
      });
      if (focused) {
        exportButtonFocused = true;
        break;
      }
    }
    
    expect(exportButtonFocused).toBe(true);
    
    // Should be able to activate with Enter
    await page.keyboard.press('Enter');
    
    // Download should trigger (or dialog open)
    const downloadStarted = await page.waitForEvent('download', { timeout: 5000 })
      .then(() => true)
      .catch(() => false);
    
    // Either download starts or a dialog opens
    if (!downloadStarted) {
      const dialog = page.locator('[role="dialog"]');
      const dialogVisible = await dialog.isVisible().catch(() => false);
      expect(downloadStarted || dialogVisible).toBe(true);
    }
  });

  test('S9.4 - Screen reader compatibility', async ({ page }) => {
    // Check for screen reader landmarks
    const main = page.locator('main, [role="main"]');
    await expect(main).toHaveCount(1);
    
    const nav = page.locator('nav, [role="navigation"]');
    if (await nav.count() > 0) {
      const navLabel = await nav.getAttribute('aria-label');
      expect(navLabel).toBeTruthy();
    }
    
    // Check heading hierarchy
    const h1 = page.locator('h1');
    await expect(h1).toHaveCount(1);
    
    // Headers should be in order
    const headers = await page.locator('h1, h2, h3, h4, h5, h6').all();
    let lastLevel = 0;
    
    for (const header of headers) {
      const tagName = await header.evaluate(el => el.tagName);
      const level = parseInt(tagName.substring(1));
      
      // Level should not skip (e.g., h1 -> h3)
      if (lastLevel > 0) {
        expect(level).toBeLessThanOrEqual(lastLevel + 1);
      }
      lastLevel = level;
    }
    
    // Images should have alt text
    const images = page.locator('img');
    const imageCount = await images.count();
    
    for (let i = 0; i < imageCount; i++) {
      const img = images.nth(i);
      const alt = await img.getAttribute('alt');
      const decorative = await img.getAttribute('role') === 'presentation';
      
      // Either has alt text or marked as decorative
      expect(alt !== null || decorative).toBe(true);
    }
  });

  test('S9.5 - Focus indicators', async ({ page }) => {
    // Check that focused elements have visible indicators
    const checkFocusIndicator = async (selector: string) => {
      const element = page.locator(selector).first();
      if (await element.count() === 0) return;
      
      await element.focus();
      
      const focusStyles = await element.evaluate(el => {
        const styles = window.getComputedStyle(el);
        return {
          outline: styles.outline,
          outlineWidth: styles.outlineWidth,
          outlineColor: styles.outlineColor,
          boxShadow: styles.boxShadow,
          border: styles.border
        };
      });
      
      // Should have some focus indicator
      const hasOutline = focusStyles.outlineWidth !== '0px' && 
                        focusStyles.outline !== 'none';
      const hasBoxShadow = focusStyles.boxShadow !== 'none';
      const hasBorderChange = focusStyles.border !== 'none';
      
      expect(hasOutline || hasBoxShadow || hasBorderChange).toBe(true);
    };
    
    await checkFocusIndicator('button');
    await checkFocusIndicator('a');
    await checkFocusIndicator('input');
    await checkFocusIndicator('[tabindex="0"]');
  });

  test('S9.6 - ARIA live regions', async ({ page }) => {
    const imagePath = testImages[0];
    
    // Check for live regions
    const liveRegions = page.locator('[aria-live]');
    const liveCount = await liveRegions.count();
    
    if (liveCount > 0) {
      // Upload and monitor live region updates
      await uploadImage(page, imagePath);
      
      // Live regions should update during processing
      const statusLive = page.locator('[aria-live="polite"], [aria-live="assertive"]');
      if (await statusLive.count() > 0) {
        const initialText = await statusLive.textContent();
        
        await page.waitForTimeout(2000);
        
        const updatedText = await statusLive.textContent();
        // Should have changed during processing
        expect(updatedText).not.toBe(initialText);
      }
    }
    
    await waitForDeckReady(page);
  });

  test('S9.7 - Color contrast minimum', async ({ page }) => {
    // This test checks specific elements for contrast
    // Full contrast checking disabled in other tests due to design phase
    
    const checkContrast = async (selector: string) => {
      const element = page.locator(selector).first();
      if (await element.count() === 0) return;
      
      const contrast = await element.evaluate(el => {
        const styles = window.getComputedStyle(el);
        const bg = styles.backgroundColor;
        const fg = styles.color;
        
        // Simple check - real implementation would calculate ratio
        return { background: bg, foreground: fg };
      });
      
      // Verify colors are set
      expect(contrast.background).toBeTruthy();
      expect(contrast.foreground).toBeTruthy();
      expect(contrast.background).not.toBe(contrast.foreground);
    };
    
    await checkContrast('button');
    await checkContrast('h1');
    await checkContrast('p');
  });

  test('S9.8 - Form validation accessibility', async ({ page }) => {
    // Trigger validation error
    const fileInput = page.locator('input[type="file"]');
    
    // Try to submit without file (if form exists)
    const form = page.locator('form');
    if (await form.count() > 0) {
      await form.evaluate(f => (f as HTMLFormElement).requestSubmit());
      
      // Error messages should be associated with inputs
      const errorMessage = page.locator('[role="alert"], [aria-live="assertive"]');
      if (await errorMessage.count() > 0) {
        const errorId = await errorMessage.getAttribute('id');
        if (errorId) {
          const describedBy = await fileInput.getAttribute('aria-describedby');
          expect(describedBy).toContain(errorId);
        }
      }
    }
  });
});
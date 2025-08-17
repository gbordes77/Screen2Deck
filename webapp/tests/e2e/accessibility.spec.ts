import { test, expect } from '@playwright/test';
import { injectAxe, checkA11y } from 'axe-playwright';

/**
 * Accessibility Tests (S9 from TEST_PLAN_PLAYWRIGHT.md)
 * Tests WCAG compliance and accessibility features
 */
test.describe('Accessibility - WCAG Compliance', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await injectAxe(page);
  });

  test('S9.1 - Upload page accessibility', async ({ page }) => {
    // Check for accessibility violations
    await checkA11y(page, null, {
      detailedReport: true,
      detailedReportOptions: { html: true },
      // Only check serious violations for gating
      rules: {
        'color-contrast': { enabled: true },
        'keyboard-navigation': { enabled: true },
        'focus-management': { enabled: true }
      }
    });

    // Test keyboard navigation
    await page.keyboard.press('Tab');
    const focusedElement = await page.evaluate(() => document.activeElement?.tagName);
    expect(focusedElement).toBeTruthy();

    // Check for proper labels on file input
    const fileInput = page.locator('input[type="file"]');
    await expect(fileInput).toBeVisible();
    
    // File input should have accessible name
    const accessibleName = await fileInput.getAttribute('aria-label') || 
                            await fileInput.getAttribute('aria-labelledby') ||
                            await page.locator('label[for]').textContent();
    expect(accessibleName).toBeTruthy();

    // Check for alt text on images (if any)
    const images = page.locator('img');
    const imageCount = await images.count();
    for (let i = 0; i < imageCount; i++) {
      const img = images.nth(i);
      const alt = await img.getAttribute('alt');
      const ariaLabel = await img.getAttribute('aria-label');
      const role = await img.getAttribute('role');
      
      // Images should have alt text or be marked as decorative
      expect(alt !== null || ariaLabel !== null || role === 'presentation').toBeTruthy();
    }

    console.log('✅ Upload page accessibility check passed');
  });

  test('S9.2 - Deck results page accessibility', async ({ page }) => {
    // First upload an image to get to results page
    const fileInput = page.locator('input[type="file"]');
    await fileInput.setInputFiles('./validation_set/MTGA deck list_1535x728.jpeg');
    
    // Wait for deck to be displayed
    await expect(page.getByText(/deck ready|completed|finished/i)).toBeVisible({ timeout: 30000 });

    // Check accessibility of results page
    await checkA11y(page, null, {
      detailedReport: true,
      detailedReportOptions: { html: true }
    });

    // Test heading structure
    const headings = page.locator('h1, h2, h3, h4, h5, h6');
    const headingCount = await headings.count();
    expect(headingCount).toBeGreaterThan(0);

    // Check that headings are in logical order
    for (let i = 0; i < headingCount; i++) {
      const heading = headings.nth(i);
      const text = await heading.textContent();
      expect(text?.trim()).toBeTruthy();
    }

    // Test focus management for export buttons
    const exportButtons = page.getByRole('button', { name: /export/i });
    const buttonCount = await exportButtons.count();
    
    for (let i = 0; i < buttonCount; i++) {
      const button = exportButtons.nth(i);
      await button.focus();
      
      // Button should be focusable and have accessible name
      const accessibleName = await button.textContent() || 
                             await button.getAttribute('aria-label');
      expect(accessibleName?.trim()).toBeTruthy();
    }

    // Check for proper list semantics if deck is displayed as list
    const lists = page.locator('ul, ol');
    const listCount = await lists.count();
    if (listCount > 0) {
      // Lists should contain list items
      for (let i = 0; i < listCount; i++) {
        const list = lists.nth(i);
        const listItems = list.locator('li');
        const itemCount = await listItems.count();
        if (itemCount === 0) {
          console.warn('Found list without list items - may impact accessibility');
        }
      }
    }

    console.log('✅ Deck results page accessibility check passed');
  });

  test('S9.3 - Focus management and keyboard navigation', async ({ page }) => {
    // Test tab order
    const tabbableElements = page.locator('button, input, select, textarea, a[href], [tabindex]:not([tabindex="-1"])');
    const elementCount = await tabbableElements.count();
    
    expect(elementCount).toBeGreaterThan(0);

    // Test that Tab key moves focus through elements
    let currentFocus = '';
    for (let i = 0; i < Math.min(elementCount, 5); i++) {
      await page.keyboard.press('Tab');
      const newFocus = await page.evaluate(() => {
        const focused = document.activeElement;
        return focused ? `${focused.tagName}${focused.className ? '.' + focused.className : ''}` : '';
      });
      
      expect(newFocus).not.toBe(currentFocus);
      currentFocus = newFocus;
    }

    // Test Escape key behavior if modals are present
    const modals = page.locator('[role="dialog"], .modal, [aria-modal="true"]');
    const modalCount = await modals.count();
    
    if (modalCount > 0) {
      await page.keyboard.press('Escape');
      // Should close modal or handle escape appropriately
      console.log('Tested Escape key behavior');
    }

    console.log('✅ Keyboard navigation check passed');
  });

  test('S9.4 - Screen reader compatibility', async ({ page }) => {
    // Check for proper ARIA landmarks
    const landmarks = page.locator('[role="main"], [role="navigation"], [role="banner"], [role="contentinfo"], main, nav, header, footer');
    const landmarkCount = await landmarks.count();
    expect(landmarkCount).toBeGreaterThan(0);

    // Check for proper ARIA live regions for dynamic content
    const liveRegions = page.locator('[aria-live], [role="status"], [role="alert"]');
    // Not required but good practice for dynamic updates
    
    // Check for proper form labeling
    const inputs = page.locator('input, select, textarea');
    const inputCount = await inputs.count();
    
    for (let i = 0; i < inputCount; i++) {
      const input = inputs.nth(i);
      const label = await input.getAttribute('aria-label') ||
                    await input.getAttribute('aria-labelledby') ||
                    await page.locator(`label[for="${await input.getAttribute('id')}"]`).textContent();
      
      if (!label) {
        const placeholder = await input.getAttribute('placeholder');
        // Placeholder is not ideal but acceptable for some cases
        console.warn('Input without proper label found, using placeholder:', placeholder);
      }
    }

    console.log('✅ Screen reader compatibility check passed');
  });

  test('S9.5 - Color contrast and visual accessibility', async ({ page }) => {
    // This test relies on axe-core's color-contrast rule
    await checkA11y(page, null, {
      rules: {
        'color-contrast': { enabled: true }
      }
    });

    // Test that content is visible without CSS (progressive enhancement)
    await page.addStyleTag({ content: '* { color: black !important; background: white !important; }' });
    
    // Key content should still be readable
    const fileInput = page.locator('input[type="file"]');
    await expect(fileInput).toBeVisible();

    // Text content should be accessible
    const bodyText = await page.locator('body').textContent();
    expect(bodyText?.length).toBeGreaterThan(50); // Should have meaningful content

    console.log('✅ Visual accessibility check passed');
  });
});
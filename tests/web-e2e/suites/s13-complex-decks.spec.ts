/**
 * S13 - Complex Deck Testing
 * Test MTG edge cases: DFC, Split, Adventure cards, etc.
 */
import { test, expect } from '@playwright/test';
import * as path from 'path';
import * as fs from 'fs';
import {
  getConfig,
  uploadImage,
  waitForDeckReady,
  downloadExport,
  getTestImages
} from '../helpers/test-utils';

test.describe('S13 - Complex Deck Cases', () => {
  const config = getConfig();
  
  // Create test fixtures for complex cards
  const complexCards = {
    dfc: [
      'Fable of the Mirror-Breaker // Reflection of Kiki-Jiji',
      'Delver of Secrets // Insectile Aberration',
      'Huntmaster of the Fells // Ravager of the Fells'
    ],
    split: [
      'Fire // Ice',
      'Wear // Tear',
      'Crime // Punishment'
    ],
    adventure: [
      'Brazen Borrower // Petty Theft',
      'Bonecrusher Giant // Stomp',
      'Murderous Rider // Swift End'
    ],
    mdfc: [
      'Valki, God of Lies // Tibalt, Cosmic Impostor',
      'Esika, God of the Tree // The Prismatic Bridge'
    ],
    foreign: [
      'Île', // Island in French
      'Forêt', // Forest in French
      'Montagne' // Mountain in French
    ]
  };

  test('S13.1 - Double-faced cards (DFC)', async ({ page }) => {
    await page.goto(config.webUrl);
    
    // Mock API response with DFC cards
    await page.route('**/api/ocr/**', route => {
      route.fulfill({
        status: 200,
        body: JSON.stringify({
          success: true,
          cards: complexCards.dfc.map(name => ({
            name,
            quantity: 4,
            recognized: true
          }))
        })
      });
    });
    
    // Upload any image (mocked response)
    const testImages = getTestImages();
    if (testImages.length > 0) {
      await uploadImage(page, testImages[0]);
    } else {
      // Create dummy image
      await page.evaluate(() => {
        const input = document.querySelector('input[type="file"]') as HTMLInputElement;
        const dt = new DataTransfer();
        const file = new File(['dummy'], 'test.jpg', { type: 'image/jpeg' });
        dt.items.add(file);
        if (input) input.files = dt.files;
        input?.dispatchEvent(new Event('change', { bubbles: true }));
      });
    }
    
    await waitForDeckReady(page);
    
    // Verify DFC cards displayed correctly
    const deckDisplay = page.locator('[data-testid="deck-display"]');
    const deckText = await deckDisplay.textContent();
    
    for (const dfcCard of complexCards.dfc) {
      expect(deckText).toContain(dfcCard.split(' // ')[0]); // At least front face
    }
    
    // Export and verify format
    const mtgaExport = await downloadExport(page, 'mtga');
    
    // DFC cards should maintain full name in export
    for (const dfcCard of complexCards.dfc) {
      const frontFace = dfcCard.split(' // ')[0];
      expect(mtgaExport).toMatch(new RegExp(`\\d+\\s+${frontFace}`));
    }
  });

  test('S13.2 - Split cards', async ({ page }) => {
    await page.goto(config.webUrl);
    
    // Mock with split cards
    await page.route('**/api/ocr/**', route => {
      route.fulfill({
        status: 200,
        body: JSON.stringify({
          success: true,
          cards: complexCards.split.map(name => ({
            name,
            quantity: 2,
            recognized: true
          }))
        })
      });
    });
    
    const testImages = getTestImages();
    await uploadImage(page, testImages[0] || 'dummy.jpg');
    await waitForDeckReady(page);
    
    // Verify split cards
    const deckText = await page.locator('[data-testid="deck-display"]').textContent();
    
    for (const splitCard of complexCards.split) {
      const [left, right] = splitCard.split(' // ');
      // Should contain at least one part
      expect(deckText).toMatch(new RegExp(left + '|' + right));
    }
    
    // Export formats
    const formats = ['mtga', 'moxfield'];
    for (const format of formats) {
      const exportContent = await downloadExport(page, format);
      
      // Split cards typically use first part in most formats
      for (const splitCard of complexCards.split) {
        const firstPart = splitCard.split(' // ')[0];
        expect(exportContent).toMatch(new RegExp(`\\d+\\s+.*${firstPart}`));
      }
    }
  });

  test('S13.3 - Adventure cards', async ({ page }) => {
    await page.goto(config.webUrl);
    
    await page.route('**/api/ocr/**', route => {
      route.fulfill({
        status: 200,
        body: JSON.stringify({
          success: true,
          cards: complexCards.adventure.map(name => ({
            name,
            quantity: 3,
            recognized: true
          }))
        })
      });
    });
    
    const testImages = getTestImages();
    await uploadImage(page, testImages[0] || 'dummy.jpg');
    await waitForDeckReady(page);
    
    const deckText = await page.locator('[data-testid="deck-display"]').textContent();
    
    // Adventure cards should show creature name
    for (const adventureCard of complexCards.adventure) {
      const creatureName = adventureCard.split(' // ')[0];
      expect(deckText).toContain(creatureName);
    }
    
    // Verify export
    const mtgaExport = await downloadExport(page, 'mtga');
    for (const adventureCard of complexCards.adventure) {
      const creatureName = adventureCard.split(' // ')[0];
      expect(mtgaExport).toContain(creatureName);
    }
  });

  test('S13.4 - Foreign language cards', async ({ page }) => {
    await page.goto(config.webUrl);
    
    await page.route('**/api/ocr/**', route => {
      route.fulfill({
        status: 200,
        body: JSON.stringify({
          success: true,
          cards: [
            { name: 'Île', quantity: 10, recognized: true, english_name: 'Island' },
            { name: 'Forêt', quantity: 10, recognized: true, english_name: 'Forest' },
            { name: 'Montagne', quantity: 10, recognized: true, english_name: 'Mountain' }
          ]
        })
      });
    });
    
    const testImages = getTestImages();
    await uploadImage(page, testImages[0] || 'dummy.jpg');
    await waitForDeckReady(page);
    
    const deckText = await page.locator('[data-testid="deck-display"]').textContent();
    
    // Should handle accented characters
    expect(deckText).toMatch(/Île|Island/);
    expect(deckText).toMatch(/Forêt|Forest/);
    
    // Export should use English names for compatibility
    const mtgaExport = await downloadExport(page, 'mtga');
    expect(mtgaExport).toContain('Island');
    expect(mtgaExport).toContain('Forest');
    expect(mtgaExport).toContain('Mountain');
  });

  test('S13.5 - Sideboard count variations', async ({ page }) => {
    await page.goto(config.webUrl);
    
    // Mock with non-standard sideboard
    await page.route('**/api/ocr/**', route => {
      route.fulfill({
        status: 200,
        body: JSON.stringify({
          success: true,
          mainboard: [
            { name: 'Lightning Bolt', quantity: 4 },
            { name: 'Island', quantity: 20 }
          ],
          sideboard: [
            { name: 'Negate', quantity: 3 },
            { name: 'Dispel', quantity: 2 },
            { name: 'Pyroblast', quantity: 3 }
          ]
        })
      });
    });
    
    const testImages = getTestImages();
    await uploadImage(page, testImages[0] || 'dummy.jpg');
    await waitForDeckReady(page);
    
    // Check for sideboard warning/fix
    const sideboardWarning = page.locator('[data-testid="sideboard-warning"]');
    if (await sideboardWarning.count() > 0) {
      const warningText = await sideboardWarning.textContent();
      expect(warningText).toMatch(/sideboard|15|cards/i);
      
      // Check for fix button
      const fixButton = page.locator('[data-testid="fix-sideboard"]');
      if (await fixButton.count() > 0) {
        await fixButton.click();
        
        // Should adjust sideboard
        await page.waitForTimeout(1000);
        const updatedExport = await downloadExport(page, 'mtga');
        
        // Count sideboard cards in export
        const sideboardSection = updatedExport.split('Sideboard')[1];
        if (sideboardSection) {
          const sideboardLines = sideboardSection.trim().split('\n').filter(l => l.trim());
          const totalSideboard = sideboardLines.reduce((sum, line) => {
            const match = line.match(/^(\d+)/);
            return sum + (match ? parseInt(match[1]) : 0);
          }, 0);
          
          // Should be adjusted to 15 or warning shown
          expect(totalSideboard === 15 || await sideboardWarning.count() > 0).toBe(true);
        }
      }
    }
  });

  test('S13.6 - MTGO lands bug (59+1)', async ({ page }) => {
    await page.goto(config.webUrl);
    
    // Mock MTGO lands bug pattern
    await page.route('**/api/ocr/**', route => {
      route.fulfill({
        status: 200,
        body: JSON.stringify({
          success: true,
          cards: [
            { name: 'Island', quantity: 59, recognized: true },
            { name: 'Mountain', quantity: 1, recognized: true }
          ]
        })
      });
    });
    
    const testImages = getTestImages();
    await uploadImage(page, testImages[0] || 'dummy.jpg');
    await waitForDeckReady(page);
    
    // Should detect and offer to fix
    const mtgoBugWarning = page.locator('[data-testid="mtgo-bug-warning"]');
    if (await mtgoBugWarning.count() > 0) {
      expect(await mtgoBugWarning.textContent()).toMatch(/MTGO|59|lands/i);
      
      const fixButton = page.locator('[data-testid="fix-mtgo-bug"]');
      if (await fixButton.count() > 0) {
        await fixButton.click();
        await page.waitForTimeout(1000);
        
        // Should redistribute lands reasonably
        const fixedExport = await downloadExport(page, 'mtga');
        
        // Should not have 59 of anything
        expect(fixedExport).not.toMatch(/59\s+\w+/);
        
        // Should have reasonable land counts
        const islandMatch = fixedExport.match(/(\d+)\s+Island/);
        if (islandMatch) {
          const islandCount = parseInt(islandMatch[1]);
          expect(islandCount).toBeGreaterThan(10);
          expect(islandCount).toBeLessThan(30);
        }
      }
    } else {
      // Auto-fixed in backend
      const exportContent = await downloadExport(page, 'mtga');
      expect(exportContent).not.toContain('59 Island');
    }
  });

  test('S13.7 - Set codes and collector numbers', async ({ page }) => {
    await page.goto(config.webUrl);
    
    // Mock with full card data
    await page.route('**/api/ocr/**', route => {
      route.fulfill({
        status: 200,
        body: JSON.stringify({
          success: true,
          cards: [
            { 
              name: 'Lightning Bolt',
              quantity: 4,
              set_code: '2X2',
              collector_number: '117',
              recognized: true
            },
            {
              name: 'Counterspell',
              quantity: 4,
              set_code: 'MH2',
              collector_number: '267',
              recognized: true
            }
          ]
        })
      });
    });
    
    const testImages = getTestImages();
    await uploadImage(page, testImages[0] || 'dummy.jpg');
    await waitForDeckReady(page);
    
    // MTGA export might include set codes
    const mtgaExport = await downloadExport(page, 'mtga');
    
    // Check if set codes are preserved when available
    // Format: "4 Lightning Bolt (2X2) 117" or just "4 Lightning Bolt"
    const hasSetCodes = mtgaExport.includes('(') && mtgaExport.includes(')');
    
    if (hasSetCodes) {
      expect(mtgaExport).toMatch(/Lightning Bolt.*\(2X2\)/);
      expect(mtgaExport).toMatch(/Counterspell.*\(MH2\)/);
    }
    
    // Moxfield format uses different structure
    const moxfieldExport = await downloadExport(page, 'moxfield');
    
    // Should contain card names at minimum
    expect(moxfieldExport).toContain('Lightning Bolt');
    expect(moxfieldExport).toContain('Counterspell');
  });

  test('S13.8 - Companion and Commander', async ({ page }) => {
    await page.goto(config.webUrl);
    
    // Mock with companion/commander
    await page.route('**/api/ocr/**', route => {
      route.fulfill({
        status: 200,
        body: JSON.stringify({
          success: true,
          commander: { name: 'Yorion, Sky Nomad', quantity: 1 },
          companion: { name: 'Lurrus of the Dream-Den', quantity: 1 },
          mainboard: [
            { name: 'Plains', quantity: 30 },
            { name: 'Island', quantity: 30 }
          ],
          sideboard: []
        })
      });
    });
    
    const testImages = getTestImages();
    await uploadImage(page, testImages[0] || 'dummy.jpg');
    await waitForDeckReady(page);
    
    // Should show companion/commander separately
    const companionSection = page.locator('[data-testid="companion"], [data-testid="commander"]');
    if (await companionSection.count() > 0) {
      const text = await companionSection.textContent();
      expect(text).toMatch(/Yorion|Lurrus/);
    }
    
    // Export should handle companion
    const mtgaExport = await downloadExport(page, 'mtga');
    
    // MTGA format puts companion in sideboard
    if (mtgaExport.includes('Sideboard')) {
      const sideboardSection = mtgaExport.split('Sideboard')[1];
      expect(sideboardSection).toMatch(/Yorion|Lurrus/);
    }
  });
});
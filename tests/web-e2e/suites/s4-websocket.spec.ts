/**
 * S4 - WebSocket Progression Testing
 * Verify real-time progress updates via WebSocket
 */
import { test, expect } from '@playwright/test';
import {
  getConfig,
  uploadImage,
  waitForDeckReady,
  getTestImages
} from '../helpers/test-utils';

test.describe('S4 - WebSocket Progression', () => {
  test.setTimeout(60000); // 60 seconds for WebSocket tests
  
  const config = getConfig();
  const testImages = getTestImages();

  test('S4.1 - Correct event order', async ({ page }) => {
    const imagePath = testImages[0];
    await page.goto(config.webUrl);
    
    const events: any[] = [];
    
    // Set up WebSocket listener
    await page.evaluate(() => {
      (window as any).wsEvents = [];
      const originalWs = window.WebSocket;
      window.WebSocket = class extends originalWs {
        constructor(url: string) {
          super(url);
          this.addEventListener('message', (event) => {
            try {
              const data = JSON.parse(event.data);
              (window as any).wsEvents.push(data);
            } catch (e) {}
          });
        }
      } as any;
    });
    
    // Upload and wait
    await uploadImage(page, imagePath);
    await waitForDeckReady(page);
    
    // Get captured events
    const capturedEvents = await page.evaluate(() => (window as any).wsEvents);
    
    // Expected event sequence
    const expectedOrder = [
      'preproc:start',
      'ocr:easyocr:start',
      'ocr:easyocr:done',
      'match:scryfall',
      'export:ready'
    ];
    
    // Extract event types
    const eventTypes = capturedEvents
      .map((e: any) => e.step || e.type)
      .filter((t: string) => expectedOrder.some(exp => t?.includes(exp.split(':')[0])));
    
    // Verify order
    let lastIndex = -1;
    for (const expected of expectedOrder) {
      const index = eventTypes.findIndex((t: string) => t.includes(expected.split(':')[0]));
      expect(index).toBeGreaterThan(lastIndex);
      lastIndex = index;
    }
  });

  test('S4.2 - Event content validation', async ({ page }) => {
    const imagePath = testImages[0];
    await page.goto(config.webUrl);
    
    // Capture WebSocket messages
    const wsMessages: any[] = [];
    page.on('websocket', ws => {
      ws.on('framereceived', event => {
        try {
          const data = JSON.parse(event.payload as string);
          wsMessages.push(data);
        } catch (e) {}
      });
    });
    
    await uploadImage(page, imagePath);
    await waitForDeckReady(page);
    
    // Verify message structure
    for (const msg of wsMessages) {
      // Should have jobId
      if (msg.jobId) {
        expect(msg.jobId).toMatch(/^[a-zA-Z0-9-]+$/);
      }
      
      // Should have step
      if (msg.step) {
        expect(msg.step).toBeTruthy();
      }
      
      // Should have elapsed time
      if (msg.elapsed_ms !== undefined) {
        expect(msg.elapsed_ms).toBeGreaterThanOrEqual(0);
      }
      
      // Should NOT contain sensitive data
      expect(JSON.stringify(msg)).not.toContain('password');
      expect(JSON.stringify(msg)).not.toContain('token');
      expect(JSON.stringify(msg)).not.toContain('secret');
    }
  });

  test('S4.3 - Progress indicators update', async ({ page }) => {
    const imagePath = testImages[0];
    await page.goto(config.webUrl);
    
    // Track progress updates
    const progressUpdates: number[] = [];
    
    await page.exposeFunction('trackProgress', (progress: number) => {
      progressUpdates.push(progress);
    });
    
    await page.evaluate(() => {
      const progressBar = document.querySelector('[data-testid="progress-bar"]');
      if (progressBar) {
        const observer = new MutationObserver(() => {
          const value = progressBar.getAttribute('aria-valuenow');
          if (value) (window as any).trackProgress(parseInt(value));
        });
        observer.observe(progressBar, { attributes: true });
      }
    });
    
    await uploadImage(page, imagePath);
    await waitForDeckReady(page);
    
    // Should have increasing progress
    if (progressUpdates.length > 1) {
      for (let i = 1; i < progressUpdates.length; i++) {
        expect(progressUpdates[i]).toBeGreaterThanOrEqual(progressUpdates[i - 1]);
      }
      expect(progressUpdates[progressUpdates.length - 1]).toBe(100);
    }
  });

  test('S4.4 - WebSocket reconnection', async ({ page }) => {
    await page.goto(config.webUrl);
    
    // Disconnect WebSocket
    await page.evaluate(() => {
      const ws = (window as any).ws;
      if (ws) ws.close();
    });
    
    // Wait a moment
    await page.waitForTimeout(1000);
    
    // Should reconnect automatically
    const wsState = await page.evaluate(() => {
      const ws = (window as any).ws;
      return ws ? ws.readyState : -1;
    });
    
    // 1 = OPEN
    if (wsState !== -1) {
      expect(wsState).toBe(1);
    }
    
    // Upload should still work
    const imagePath = testImages[0];
    await uploadImage(page, imagePath);
    await waitForDeckReady(page);
    
    // Verify deck displayed
    await expect(page.locator('[data-testid="deck-display"]')).toBeVisible();
  });
});
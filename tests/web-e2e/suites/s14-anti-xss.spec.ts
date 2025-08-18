/**
 * S14 - Anti-XSS Security Testing
 * Verify protection against XSS attacks
 */
import { test, expect } from '@playwright/test';
import {
  getConfig,
  uploadImage,
  waitForDeckReady,
  getTestImages
} from '../helpers/test-utils';

test.describe('S14 - Anti-XSS Security', () => {
  const config = getConfig();
  
  // XSS payloads to test
  const xssPayloads = [
    '<script>alert("XSS")</script>',
    '<img src=x onerror=alert("XSS")>',
    '<svg onload=alert("XSS")>',
    'javascript:alert("XSS")',
    '<iframe src="javascript:alert(\'XSS\')">',
    '</div><script>alert("XSS")</script><div>',
    '"><script>alert("XSS")</script>',
    '\';alert("XSS");//',
    '<img src="x" onerror="alert(1)">',
    '<body onload=alert("XSS")>',
    '<<SCRIPT>alert("XSS");//<</SCRIPT>',
    '<script>alert(String.fromCharCode(88,83,83))</script>',
    '<META HTTP-EQUIV="refresh" CONTENT="0;url=javascript:alert(\'XSS\');">',
    '<STYLE>li {list-style-image: url("javascript:alert(\'XSS\')");}</STYLE>',
    '\\x3cscript\\x3ealert("XSS")\\x3c/script\\x3e'
  ];

  test.beforeEach(async ({ page }) => {
    // Monitor for XSS execution
    page.on('dialog', async dialog => {
      // If any dialog appears, XSS succeeded (fail test)
      console.error('XSS Alert detected:', dialog.message());
      await dialog.dismiss();
      throw new Error(`XSS executed: ${dialog.message()}`);
    });
    
    // Monitor console for XSS
    page.on('console', msg => {
      if (msg.text().includes('XSS')) {
        throw new Error(`XSS in console: ${msg.text()}`);
      }
    });
  });

  test('S14.1 - XSS in card names', async ({ page }) => {
    await page.goto(config.webUrl);
    
    // Mock OCR response with XSS payloads in card names
    await page.route('**/api/ocr/**', route => {
      route.fulfill({
        status: 200,
        body: JSON.stringify({
          success: true,
          cards: xssPayloads.slice(0, 5).map(payload => ({
            name: payload,
            quantity: 1,
            recognized: false
          }))
        })
      });
    });
    
    const testImages = getTestImages('day0');
    await uploadImage(page, testImages[0] || 'dummy.jpg');
    await waitForDeckReady(page);
    
    // Wait to see if XSS executes
    await page.waitForTimeout(2000);
    
    // Verify XSS payloads are escaped in DOM
    const deckDisplay = page.locator('[data-testid="deck-display"]');
    const deckHTML = await deckDisplay.innerHTML();
    
    // Should not contain executable script tags
    expect(deckHTML).not.toContain('<script>');
    expect(deckHTML).not.toContain('onerror=');
    expect(deckHTML).not.toContain('onload=');
    expect(deckHTML).not.toContain('javascript:');
    
    // Text content should show escaped version
    const deckText = await deckDisplay.textContent();
    
    // Should contain the literal text (escaped)
    for (const payload of xssPayloads.slice(0, 5)) {
      // The payload should be visible as text, not executed
      const isTextVisible = deckText?.includes('<script>') || 
                           deckText?.includes('&lt;script&gt;') ||
                           deckText?.includes(payload.replace(/<[^>]*>/g, ''));
      expect(isTextVisible || deckHTML.includes('&lt;')).toBe(true);
    }
  });

  test('S14.2 - XSS in export content', async ({ page }) => {
    await page.goto(config.webUrl);
    
    // Mock with XSS in card data
    await page.route('**/api/ocr/**', route => {
      route.fulfill({
        status: 200,
        body: JSON.stringify({
          success: true,
          cards: [
            {
              name: '<img src=x onerror=alert("XSS")>',
              quantity: 4,
              set_code: '"><script>alert("XSS")</script>',
              recognized: false
            }
          ]
        })
      });
    });
    
    const testImages = getTestImages('day0');
    await uploadImage(page, testImages[0] || 'dummy.jpg');
    await waitForDeckReady(page);
    
    // Download export
    const downloadPromise = page.waitForEvent('download');
    await page.click('[data-testid="export-mtga"]');
    const download = await downloadPromise;
    
    // Read downloaded content
    const stream = await download.createReadStream();
    let content = '';
    await new Promise((resolve, reject) => {
      stream?.on('data', chunk => content += chunk);
      stream?.on('end', resolve);
      stream?.on('error', reject);
    });
    
    // Export should contain escaped/sanitized text
    expect(content).not.toContain('<script>');
    expect(content).not.toContain('onerror=');
    
    // Should be plain text
    expect(content).toMatch(/^[\w\s\d\-\(\)\/\n]+$/m);
  });

  test('S14.3 - XSS via file upload metadata', async ({ page }) => {
    await page.goto(config.webUrl);
    
    // Create file with XSS in filename
    await page.evaluate(() => {
      const xssFilename = '"><img src=x onerror=alert("XSS")>.jpg';
      const file = new File(['test'], xssFilename, { type: 'image/jpeg' });
      const dt = new DataTransfer();
      dt.items.add(file);
      const input = document.querySelector('input[type="file"]') as HTMLInputElement;
      if (input) {
        input.files = dt.files;
        input.dispatchEvent(new Event('change', { bubbles: true }));
      }
    });
    
    await page.waitForTimeout(2000);
    
    // Check if filename is displayed
    const filenameDisplay = page.locator('[data-testid="filename"], .filename');
    if (await filenameDisplay.count() > 0) {
      const displayedName = await filenameDisplay.textContent();
      
      // Should not execute XSS
      expect(displayedName).not.toContain('<img');
      expect(displayedName).not.toContain('onerror');
      
      // Should show sanitized version
      const html = await filenameDisplay.innerHTML();
      expect(html).not.toContain('onerror=');
    }
  });

  test('S14.4 - XSS in URL parameters', async ({ page }) => {
    // Try XSS via URL params
    const xssUrl = `${config.webUrl}?card=<script>alert("XSS")</script>&deck="><img src=x onerror=alert(1)>`;
    
    await page.goto(xssUrl);
    await page.waitForTimeout(2000);
    
    // Should not execute
    // Check if params are displayed anywhere
    const pageContent = await page.content();
    
    // Should not have unescaped script tags
    expect(pageContent).not.toMatch(/<script>alert\("XSS"\)<\/script>/);
    expect(pageContent).not.toContain('onerror=alert');
  });

  test('S14.5 - XSS in WebSocket messages', async ({ page }) => {
    await page.goto(config.webUrl);
    
    // Inject XSS via WebSocket if possible
    await page.evaluate(() => {
      const ws = (window as any).ws;
      if (ws && ws.send) {
        // Try to send XSS payload
        ws.send(JSON.stringify({
          type: 'message',
          content: '<script>alert("XSS")</script>'
        }));
      }
    });
    
    await page.waitForTimeout(2000);
    
    // Check status messages
    const statusMessages = page.locator('[data-testid="status-message"], .status');
    if (await statusMessages.count() > 0) {
      const html = await statusMessages.innerHTML();
      expect(html).not.toContain('<script>');
      expect(html).not.toContain('onerror=');
    }
  });

  test('S14.6 - XSS in error messages', async ({ page }) => {
    await page.goto(config.webUrl);
    
    // Trigger error with XSS payload
    await page.route('**/api/ocr/**', route => {
      route.fulfill({
        status: 500,
        body: JSON.stringify({
          error: '<img src=x onerror=alert("XSS")>',
          details: '"><script>alert("XSS")</script>'
        })
      });
    });
    
    const testImages = getTestImages('day0');
    await uploadImage(page, testImages[0] || 'dummy.jpg');
    
    // Wait for error display
    await page.waitForTimeout(3000);
    
    const errorMessage = page.locator('[data-testid="error-message"], .error');
    if (await errorMessage.count() > 0) {
      const errorHTML = await errorMessage.innerHTML();
      const errorText = await errorMessage.textContent();
      
      // Should not contain executable code
      expect(errorHTML).not.toContain('onerror=');
      expect(errorHTML).not.toContain('<script>');
      
      // Should show escaped text
      expect(errorText).toMatch(/&lt;|<img|script/);
    }
  });

  test('S14.7 - Content Security Policy', async ({ page }) => {
    const response = await page.goto(config.webUrl);
    
    if (response) {
      const csp = response.headers()['content-security-policy'];
      
      if (csp) {
        // Should have restrictive CSP
        expect(csp).toMatch(/script-src/);
        expect(csp).not.toContain('unsafe-inline');
        expect(csp).not.toContain('unsafe-eval');
      }
    }
    
    // Try inline script injection
    await page.evaluate(() => {
      const script = document.createElement('script');
      script.textContent = 'window.xssTest = "failed"';
      document.head.appendChild(script);
    });
    
    // Check if it executed
    const xssTest = await page.evaluate(() => (window as any).xssTest);
    
    // With proper CSP, inline script should not execute
    if (csp && csp.includes('script-src')) {
      expect(xssTest).toBeUndefined();
    }
  });

  test('S14.8 - DOM-based XSS prevention', async ({ page }) => {
    await page.goto(config.webUrl);
    
    // Try DOM manipulation with XSS
    const hasXSS = await page.evaluate(() => {
      try {
        // Try to inject via innerHTML
        const div = document.createElement('div');
        div.innerHTML = '<img src=x onerror=window.xssFired=true>';
        document.body.appendChild(div);
        
        // Try via document.write
        document.write('<script>window.xssWrite=true</script>');
        
        return {
          fired: (window as any).xssFired,
          write: (window as any).xssWrite
        };
      } catch (e) {
        return { error: e.message };
      }
    });
    
    // Should not execute
    expect(hasXSS.fired).not.toBe(true);
    expect(hasXSS.write).not.toBe(true);
  });

  test('S14.9 - JSON injection prevention', async ({ page }) => {
    await page.goto(config.webUrl);
    
    // Mock response with JSON injection attempt
    await page.route('**/api/ocr/**', route => {
      route.fulfill({
        status: 200,
        // Malformed JSON with injection
        body: '{"success":true,"cards":[{"name":"test"}</script><script>alert("XSS")</script>"}]}'
      });
    });
    
    const testImages = getTestImages('day0');
    
    // Should handle malformed JSON safely
    let errorOccurred = false;
    page.on('pageerror', () => {
      errorOccurred = true;
    });
    
    await uploadImage(page, testImages[0] || 'dummy.jpg');
    await page.waitForTimeout(3000);
    
    // Should show error, not execute XSS
    const errorDisplay = page.locator('[data-testid="error-message"]');
    if (!errorOccurred) {
      // If no error, data should be escaped
      const deckDisplay = page.locator('[data-testid="deck-display"]');
      const html = await deckDisplay.innerHTML();
      expect(html).not.toContain('<script>');
    }
  });

  test('S14.10 - Stored XSS prevention', async ({ page }) => {
    await page.goto(config.webUrl);
    
    // Submit XSS payload
    await page.route('**/api/ocr/**', route => {
      route.fulfill({
        status: 200,
        body: JSON.stringify({
          success: true,
          jobId: '"><script>alert("XSS")</script>',
          cards: [{
            name: 'Stored XSS <script>alert(1)</script>',
            quantity: 1
          }]
        })
      });
    });
    
    const testImages = getTestImages('day0');
    await uploadImage(page, testImages[0] || 'dummy.jpg');
    await waitForDeckReady(page);
    
    // Reload page (simulate stored XSS)
    await page.reload();
    
    // If job ID is in URL or localStorage
    const url = page.url();
    expect(url).not.toContain('<script>');
    
    const localStorage = await page.evaluate(() => {
      const stored = window.localStorage.getItem('lastJob');
      return stored;
    });
    
    if (localStorage) {
      expect(localStorage).not.toContain('<script>');
      expect(localStorage).not.toContain('onerror=');
    }
  });
});
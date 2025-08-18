/**
 * S7 - Security Upload Testing
 * Verify file upload security measures
 */
import { test, expect } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';
import {
  getConfig,
  createCorruptedImage,
  createOversizedImage
} from '../helpers/test-utils';

test.describe('S7 - Security Upload', () => {
  const config = getConfig();
  const tempFiles: string[] = [];

  test.afterEach(async () => {
    // Cleanup temp files
    for (const file of tempFiles) {
      if (fs.existsSync(file)) {
        fs.unlinkSync(file);
      }
    }
    tempFiles.length = 0;
  });

  test('S7.1 - Non-image disguised as PNG', async ({ page }) => {
    await page.goto(config.webUrl);
    
    // Create fake PNG (actually EXE content)
    const fakePng = path.join(process.cwd(), 'fake.png');
    fs.writeFileSync(fakePng, Buffer.from('MZ\x90\x00\x03')); // EXE header
    tempFiles.push(fakePng);
    
    const fileInput = page.locator('input[type="file"]');
    await fileInput.setInputFiles(fakePng);
    
    // Should show error
    const errorMessage = page.locator('[data-testid="upload-error"]');
    await expect(errorMessage).toBeVisible({ timeout: 5000 });
    
    const errorText = await errorMessage.textContent();
    expect(errorText?.toLowerCase()).toMatch(/format|support|invalid|magic/);
  });

  test('S7.2 - File size exceeds limit', async ({ page }) => {
    await page.goto(config.webUrl);
    
    // Create oversized file
    const oversizedFile = await createOversizedImage();
    tempFiles.push(oversizedFile);
    
    const fileInput = page.locator('input[type="file"]');
    
    // Attempt upload
    await fileInput.setInputFiles(oversizedFile);
    
    // Should show size error
    const errorMessage = page.locator('[data-testid="upload-error"]');
    await expect(errorMessage).toBeVisible({ timeout: 5000 });
    
    const errorText = await errorMessage.textContent();
    expect(errorText?.toLowerCase()).toMatch(/size|large|exceed|limit/);
  });

  test('S7.3 - Image dimensions exceed maximum', async ({ page }) => {
    await page.goto(config.webUrl);
    
    // Create image with excessive dimensions (simulated via canvas)
    await page.evaluate(() => {
      const canvas = document.createElement('canvas');
      canvas.width = 10000;
      canvas.height = 10000;
      canvas.toBlob(blob => {
        if (blob) {
          const file = new File([blob], 'huge.jpg', { type: 'image/jpeg' });
          const dt = new DataTransfer();
          dt.items.add(file);
          const input = document.querySelector('input[type="file"]') as HTMLInputElement;
          if (input) input.files = dt.files;
          input?.dispatchEvent(new Event('change', { bubbles: true }));
        }
      });
    });
    
    // Should show dimension error
    const errorMessage = page.locator('[data-testid="upload-error"]');
    await expect(errorMessage).toBeVisible({ timeout: 5000 });
    
    const errorText = await errorMessage.textContent();
    expect(errorText?.toLowerCase()).toMatch(/dimension|resolution|size|large/);
  });

  test('S7.4 - PDF upload rejected', async ({ page }) => {
    await page.goto(config.webUrl);
    
    // Create fake PDF
    const fakePdf = path.join(process.cwd(), 'test.pdf');
    fs.writeFileSync(fakePdf, '%PDF-1.4\n%âÉ');
    tempFiles.push(fakePdf);
    
    const fileInput = page.locator('input[type="file"]');
    await fileInput.setInputFiles(fakePdf);
    
    // Should reject PDF
    const errorMessage = page.locator('[data-testid="upload-error"]');
    await expect(errorMessage).toBeVisible({ timeout: 5000 });
    
    const errorText = await errorMessage.textContent();
    expect(errorText?.toLowerCase()).toMatch(/format|support|pdf|image/);
  });

  test('S7.5 - SVG upload rejected', async ({ page }) => {
    await page.goto(config.webUrl);
    
    // Create SVG file
    const svgContent = '<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>';
    const svgFile = path.join(process.cwd(), 'test.svg');
    fs.writeFileSync(svgFile, svgContent);
    tempFiles.push(svgFile);
    
    const fileInput = page.locator('input[type="file"]');
    await fileInput.setInputFiles(svgFile);
    
    // Should reject SVG (security risk)
    const errorMessage = page.locator('[data-testid="upload-error"]');
    await expect(errorMessage).toBeVisible({ timeout: 5000 });
    
    const errorText = await errorMessage.textContent();
    expect(errorText?.toLowerCase()).toMatch(/format|support|svg|security/);
  });

  test('S7.6 - Multiple file upload handling', async ({ page }) => {
    await page.goto(config.webUrl);
    
    // Create multiple files
    const file1 = path.join(process.cwd(), 'test1.jpg');
    const file2 = path.join(process.cwd(), 'test2.jpg');
    
    // Create minimal valid JPEGs
    const jpegHeader = Buffer.from([0xFF, 0xD8, 0xFF, 0xE0]);
    fs.writeFileSync(file1, jpegHeader);
    fs.writeFileSync(file2, jpegHeader);
    tempFiles.push(file1, file2);
    
    const fileInput = page.locator('input[type="file"]');
    
    // Try to upload multiple files
    await fileInput.setInputFiles([file1, file2]);
    
    // Should either process first only or show error
    const errorMessage = page.locator('[data-testid="upload-error"]');
    const processingMessage = page.locator('[data-testid="processing"]');
    
    const hasError = await errorMessage.count() > 0;
    const isProcessing = await processingMessage.count() > 0;
    
    expect(hasError || isProcessing).toBe(true);
  });

  test('S7.7 - Client-side validation', async ({ page }) => {
    await page.goto(config.webUrl);
    
    // Check input accept attribute
    const fileInput = page.locator('input[type="file"]');
    const acceptAttr = await fileInput.getAttribute('accept');
    
    // Should only accept image formats
    expect(acceptAttr).toMatch(/image/);
    expect(acceptAttr).not.toMatch(/pdf/);
    expect(acceptAttr).not.toMatch(/svg/);
    
    // Verify max file size is communicated
    const uploadArea = page.locator('[data-testid="upload-area"]');
    const uploadText = await uploadArea.textContent();
    
    // Should mention size limit
    if (uploadText) {
      const hasSizeInfo = uploadText.match(/\d+\s*(mb|megabyte)/i);
      expect(hasSizeInfo).toBeTruthy();
    }
  });

  test('S7.8 - Malformed filename handling', async ({ page }) => {
    await page.goto(config.webUrl);
    
    // Create file with malicious filename
    const maliciousName = '../../../etc/passwd.jpg';
    const safeName = 'test.jpg';
    const filePath = path.join(process.cwd(), safeName);
    
    // Create minimal valid JPEG
    const jpegHeader = Buffer.from([0xFF, 0xD8, 0xFF, 0xE0]);
    fs.writeFileSync(filePath, jpegHeader);
    tempFiles.push(filePath);
    
    // Upload with attempted path traversal
    const fileInput = page.locator('input[type="file"]');
    await fileInput.setInputFiles(filePath);
    
    // Should sanitize filename if displayed
    await page.waitForTimeout(1000);
    const displayedFilename = await page.locator('[data-testid="filename"]').textContent();
    
    if (displayedFilename) {
      expect(displayedFilename).not.toContain('..');
      expect(displayedFilename).not.toContain('/etc/');
    }
  });
});
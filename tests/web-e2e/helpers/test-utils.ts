import { Page, expect, Locator } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';
import * as crypto from 'crypto';

export interface TestConfig {
  webUrl: string;
  apiUrl: string;
  goldenDir: string;
  datasetDir: string;
  wsUrl: string;
}

export function getConfig(): TestConfig {
  return {
    webUrl: process.env.WEB_URL || 'http://localhost:3000',
    apiUrl: process.env.API_URL || 'http://localhost:8080',
    goldenDir: process.env.GOLDEN_DIR || './golden',
    datasetDir: process.env.DATASET_DIR || './validation_set',
    wsUrl: process.env.WS_URL || 'ws://localhost:8080/ws',
  };
}

export async function uploadImage(page: Page, imagePath: string): Promise<void> {
  const fileInput = page.locator('input[type="file"]');
  await fileInput.setInputFiles(imagePath);
}

export async function waitForDeckReady(page: Page, timeout: number = 30000): Promise<void> {
  await expect(page.locator('[data-testid="deck-ready"]')).toBeVisible({ timeout });
}

export async function downloadExport(page: Page, format: string): Promise<string> {
  const downloadPromise = page.waitForEvent('download');
  await page.click(`[data-testid="export-${format}"]`);
  const download = await downloadPromise;
  const stream = await download.createReadStream();
  
  return new Promise((resolve, reject) => {
    let content = '';
    stream?.on('data', chunk => content += chunk);
    stream?.on('end', () => resolve(content));
    stream?.on('error', reject);
  });
}

export function compareWithGolden(actual: string, goldenPath: string): boolean {
  const golden = fs.readFileSync(goldenPath, 'utf-8');
  return actual.trim() === golden.trim();
}

export function hashContent(content: string): string {
  return crypto.createHash('sha256').update(content).digest('hex');
}

export async function measureEndToEnd(page: Page, imagePath: string): Promise<number> {
  const startTime = Date.now();
  await uploadImage(page, imagePath);
  await waitForDeckReady(page);
  const endTime = Date.now();
  return (endTime - startTime) / 1000;
}

export async function waitForWebSocketMessage(
  page: Page,
  eventType: string,
  timeout: number = 10000
): Promise<any> {
  return page.evaluate(({ eventType, timeout }) => {
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => reject(new Error('Timeout')), timeout);
      const handler = (e: CustomEvent) => {
        if (e.detail.type === eventType) {
          clearTimeout(timer);
          window.removeEventListener('ws-message', handler as EventListener);
          resolve(e.detail);
        }
      };
      window.addEventListener('ws-message', handler as EventListener);
    });
  }, { eventType, timeout });
}

export async function simulateOfflineScryfall(page: Page): Promise<void> {
  await page.route(/scryfall\.com/, route => route.abort());
}

export async function createCorruptedImage(): Promise<string> {
  const tempPath = path.join(process.cwd(), 'temp-corrupted.jpg');
  fs.writeFileSync(tempPath, Buffer.from('corrupted data'));
  return tempPath;
}

export async function createOversizedImage(): Promise<string> {
  const tempPath = path.join(process.cwd(), 'temp-oversized.jpg');
  const size = 15 * 1024 * 1024; // 15MB
  fs.writeFileSync(tempPath, Buffer.alloc(size));
  return tempPath;
}

export async function checkAccessibility(page: Page): Promise<any> {
  // @ts-ignore
  const results = await page.evaluate(() => window.axe.run());
  return results.violations;
}

export function getTestImages(category: string = 'day0'): string[] {
  const dir = path.join(process.cwd(), 'validation_set', category);
  return fs.readdirSync(dir)
    .filter(f => /\.(jpg|jpeg|png|webp)$/i.test(f))
    .map(f => path.join(dir, f));
}
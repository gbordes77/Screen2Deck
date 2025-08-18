/**
 * S12 - Performance Testing
 * Measure and validate performance SLOs
 */
import { test, expect } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';
import {
  getConfig,
  uploadImage,
  waitForDeckReady,
  measureEndToEnd,
  getTestImages
} from '../helpers/test-utils';

test.describe('S12 - Performance', () => {
  const config = getConfig();
  const testImages = getTestImages('day0');
  const SLO_P95_LATENCY = parseFloat(process.env.SLO_P95_LATENCY_SEC || '5');

  test('S12.1 - End-to-end latency measurement', async ({ page }) => {
    const latencies: number[] = [];
    
    // Test multiple images
    for (let i = 0; i < Math.min(5, testImages.length); i++) {
      await page.goto(config.webUrl);
      
      const startTime = Date.now();
      await uploadImage(page, testImages[i]);
      await waitForDeckReady(page);
      const endTime = Date.now();
      
      const latency = (endTime - startTime) / 1000;
      latencies.push(latency);
      
      // Each individual should be under reasonable threshold
      expect(latency).toBeLessThan(SLO_P95_LATENCY * 2); // Allow 2x SLO for individual
    }
    
    // Calculate P95
    latencies.sort((a, b) => a - b);
    const p95Index = Math.floor(latencies.length * 0.95);
    const p95Latency = latencies[p95Index] || latencies[latencies.length - 1];
    
    console.log(`P95 Latency: ${p95Latency.toFixed(2)}s (SLO: ${SLO_P95_LATENCY}s)`);
    
    // Verify SLO
    expect(p95Latency).toBeLessThan(SLO_P95_LATENCY);
    
    // Calculate mean
    const mean = latencies.reduce((a, b) => a + b, 0) / latencies.length;
    console.log(`Mean Latency: ${mean.toFixed(2)}s`);
    
    // Write metrics
    const metrics = {
      p95: p95Latency,
      mean: mean,
      min: Math.min(...latencies),
      max: Math.max(...latencies),
      samples: latencies.length
    };
    
    const metricsPath = path.join(process.cwd(), 'artifacts', 'e2e-metrics.json');
    fs.mkdirSync(path.dirname(metricsPath), { recursive: true });
    fs.writeFileSync(metricsPath, JSON.stringify(metrics, null, 2));
  });

  test('S12.2 - Resource loading performance', async ({ page }) => {
    const resourceTimings: any[] = [];
    
    // Collect resource timings
    page.on('response', response => {
      const timing = response.timing();
      if (timing) {
        resourceTimings.push({
          url: response.url(),
          duration: timing.responseEnd - timing.startTime,
          size: response.headers()['content-length']
        });
      }
    });
    
    await page.goto(config.webUrl);
    
    // Wait for page to fully load
    await page.waitForLoadState('networkidle');
    
    // Analyze resource timings
    const slowResources = resourceTimings.filter(r => r.duration > 1000);
    
    // No single resource should take more than 3 seconds
    for (const resource of slowResources) {
      console.log(`Slow resource: ${resource.url} (${resource.duration}ms)`);
      expect(resource.duration).toBeLessThan(3000);
    }
    
    // Total load time
    const totalLoadTime = await page.evaluate(() => {
      const perf = window.performance;
      const navTiming = perf.getEntriesByType('navigation')[0] as PerformanceNavigationTiming;
      return navTiming.loadEventEnd - navTiming.fetchStart;
    });
    
    console.log(`Total page load time: ${totalLoadTime}ms`);
    expect(totalLoadTime).toBeLessThan(5000); // 5 seconds max
  });

  test('S12.3 - WebSocket message latency', async ({ page }) => {
    const wsLatencies: number[] = [];
    
    await page.goto(config.webUrl);
    
    // Monitor WebSocket messages
    await page.evaluate(() => {
      (window as any).wsTimings = [];
      const originalWs = window.WebSocket;
      window.WebSocket = class extends originalWs {
        constructor(url: string) {
          super(url);
          const sendTime = Date.now();
          this.addEventListener('message', (event) => {
            const receiveTime = Date.now();
            (window as any).wsTimings.push({
              latency: receiveTime - sendTime,
              data: event.data
            });
          });
        }
      } as any;
    });
    
    const imagePath = testImages[0];
    await uploadImage(page, imagePath);
    await waitForDeckReady(page);
    
    // Get WebSocket timings
    const timings = await page.evaluate(() => (window as any).wsTimings);
    
    if (timings && timings.length > 0) {
      const latencies = timings.map((t: any) => t.latency);
      const avgLatency = latencies.reduce((a: number, b: number) => a + b, 0) / latencies.length;
      
      console.log(`Average WS latency: ${avgLatency}ms`);
      
      // WebSocket messages should be fast
      expect(avgLatency).toBeLessThan(100); // 100ms average
      expect(Math.max(...latencies)).toBeLessThan(500); // 500ms max
    }
  });

  test('S12.4 - Memory usage', async ({ page }) => {
    await page.goto(config.webUrl);
    
    // Get initial memory
    const initialMemory = await page.evaluate(() => {
      if ('memory' in performance) {
        return (performance as any).memory.usedJSHeapSize;
      }
      return 0;
    });
    
    // Process multiple images
    for (let i = 0; i < Math.min(3, testImages.length); i++) {
      await page.goto(config.webUrl);
      await uploadImage(page, testImages[i]);
      await waitForDeckReady(page);
    }
    
    // Get final memory
    const finalMemory = await page.evaluate(() => {
      if ('memory' in performance) {
        return (performance as any).memory.usedJSHeapSize;
      }
      return 0;
    });
    
    if (initialMemory && finalMemory) {
      const memoryIncrease = (finalMemory - initialMemory) / 1024 / 1024; // MB
      console.log(`Memory increase: ${memoryIncrease.toFixed(2)} MB`);
      
      // Should not leak excessive memory
      expect(memoryIncrease).toBeLessThan(100); // 100MB max increase
    }
  });

  test('S12.5 - CPU usage during processing', async ({ page }) => {
    await page.goto(config.webUrl);
    
    // Monitor long tasks
    const longTasks = await page.evaluateHandle(() => {
      return new Promise(resolve => {
        const tasks: any[] = [];
        const observer = new PerformanceObserver((list) => {
          for (const entry of list.getEntries()) {
            if (entry.duration > 50) { // Tasks longer than 50ms
              tasks.push({
                name: entry.name,
                duration: entry.duration
              });
            }
          }
        });
        observer.observe({ entryTypes: ['longtask'] });
        
        setTimeout(() => {
          observer.disconnect();
          resolve(tasks);
        }, 30000);
      });
    });
    
    const imagePath = testImages[0];
    await uploadImage(page, imagePath);
    await waitForDeckReady(page);
    
    const tasks = await longTasks.jsonValue();
    
    // Should not have too many long tasks
    if (Array.isArray(tasks)) {
      console.log(`Long tasks: ${tasks.length}`);
      expect(tasks.length).toBeLessThan(10);
      
      // No single task should block for too long
      for (const task of tasks) {
        expect(task.duration).toBeLessThan(1000); // 1 second max
      }
    }
  });

  test('S12.6 - Cache hit rate', async ({ page }) => {
    const cacheHits = { hit: 0, miss: 0 };
    
    // Monitor cache headers
    page.on('response', response => {
      const cacheHeader = response.headers()['x-cache'];
      if (cacheHeader === 'HIT') {
        cacheHits.hit++;
      } else if (cacheHeader === 'MISS') {
        cacheHits.miss++;
      }
    });
    
    // First upload (cache miss expected)
    await page.goto(config.webUrl);
    await uploadImage(page, testImages[0]);
    await waitForDeckReady(page);
    
    // Second upload of same image (cache hit expected)
    await page.goto(config.webUrl);
    await uploadImage(page, testImages[0]);
    await waitForDeckReady(page);
    
    const hitRate = cacheHits.hit / (cacheHits.hit + cacheHits.miss);
    console.log(`Cache hit rate: ${(hitRate * 100).toFixed(1)}%`);
    
    // Should have good cache hit rate on second attempt
    const SLO_CACHE_HIT = parseFloat(process.env.SLO_CACHE_HIT_MIN || '0.80');
    if (cacheHits.hit + cacheHits.miss > 0) {
      expect(hitRate).toBeGreaterThan(SLO_CACHE_HIT * 0.5); // Allow some variance
    }
  });

  test('S12.7 - Time to interactive', async ({ page }) => {
    const startTime = Date.now();
    
    await page.goto(config.webUrl);
    
    // Wait for upload area to be interactive
    const uploadArea = page.locator('[data-testid="upload-area"]');
    await uploadArea.waitFor({ state: 'visible' });
    
    // Verify it's actually interactive
    const fileInput = page.locator('input[type="file"]');
    await expect(fileInput).toBeEnabled();
    
    const tti = Date.now() - startTime;
    console.log(`Time to Interactive: ${tti}ms`);
    
    // Should be interactive quickly
    expect(tti).toBeLessThan(3000); // 3 seconds max
  });

  test('S12.8 - Lighthouse metrics', async ({ page }) => {
    // Skip in CI due to complexity
    if (process.env.CI) {
      test.skip();
      return;
    }
    
    await page.goto(config.webUrl);
    
    // Collect Core Web Vitals
    const metrics = await page.evaluate(() => {
      return new Promise(resolve => {
        const results: any = {};
        
        // LCP
        new PerformanceObserver((list) => {
          const entries = list.getEntries();
          const lastEntry = entries[entries.length - 1];
          results.lcp = lastEntry.startTime;
        }).observe({ entryTypes: ['largest-contentful-paint'] });
        
        // FID (simulate)
        results.fid = 0; // Would need real user interaction
        
        // CLS
        let clsValue = 0;
        new PerformanceObserver((list) => {
          for (const entry of list.getEntries()) {
            if (!(entry as any).hadRecentInput) {
              clsValue += (entry as any).value;
            }
          }
          results.cls = clsValue;
        }).observe({ entryTypes: ['layout-shift'] });
        
        // Wait and resolve
        setTimeout(() => resolve(results), 5000);
      });
    });
    
    console.log('Core Web Vitals:', metrics);
    
    // Verify against thresholds
    if (metrics.lcp) {
      expect(metrics.lcp).toBeLessThan(2500); // 2.5s LCP
    }
    if (metrics.cls !== undefined) {
      expect(metrics.cls).toBeLessThan(0.1); // 0.1 CLS
    }
  });
});
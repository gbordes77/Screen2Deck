import { defineConfig, devices } from '@playwright/test';
import * as path from 'path';

/**
 * Screen2Deck E2E Test Configuration
 * Full implementation of TEST_PLAN_PLAYWRIGHT.md
 */
export default defineConfig({
  testDir: './tests/web-e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 1,
  workers: process.env.CI ? 1 : undefined,
  reporter: [
    ['list'],
    ['junit', { outputFile: 'reports/e2e-junit.xml' }],
    ['html', { outputFolder: 'playwright-report', open: 'never' }]
  ],
  
  use: {
    baseURL: process.env.WEB_URL || 'http://localhost:3000',
    trace: 'on-first-retry',
    video: 'retain-on-failure',
    screenshot: 'only-on-failure',
    actionTimeout: 15000,
    navigationTimeout: 30000,
  },

  // Global timeout
  timeout: 30000,
  expect: {
    timeout: 10000,
  },

  // Projects for different browsers and devices
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
    {
      name: 'firefox',
      use: { ...devices['Desktop Firefox'] },
    },
    {
      name: 'webkit',
      use: { ...devices['Desktop Safari'] },
    },
    {
      name: 'mobile',
      use: { ...devices['Pixel 7'] },
    },
    {
      name: 'all',
      use: { ...devices['Desktop Chrome'] },
    },
    // Network throttling tests
    {
      name: 'slow-3g',
      use: {
        ...devices['Desktop Chrome'],
        offline: false,
        // Simulate slow network
        extraHTTPHeaders: {
          'X-Test-Network': 'slow-3g'
        }
      },
    },
  ],

  // Web server configuration for local testing
  webServer: process.env.CI ? undefined : {
    command: 'docker compose --profile core up',
    url: 'http://localhost:3000',
    reuseExistingServer: !process.env.CI,
    timeout: 120000,
  },
});
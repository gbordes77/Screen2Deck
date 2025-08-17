import { APIRequestContext } from '@playwright/test';

/**
 * API Client for E2E Tests
 * Provides typed methods for interacting with the Screen2Deck API
 */
export class APIClient {
  constructor(private request: APIRequestContext, private baseURL: string = process.env.API_URL || 'http://localhost:8080') {}

  async uploadImage(filePath: string): Promise<{ jobId: string }> {
    const response = await this.request.post(`${this.baseURL}/api/ocr/upload`, {
      multipart: {
        file: filePath
      }
    });

    if (!response.ok()) {
      throw new Error(`Upload failed: ${response.status()} ${await response.text()}`);
    }

    return await response.json();
  }

  async getJobStatus(jobId: string): Promise<any> {
    const response = await this.request.get(`${this.baseURL}/api/ocr/status/${jobId}`);
    
    if (!response.ok()) {
      throw new Error(`Status check failed: ${response.status()}`);
    }

    return await response.json();
  }

  async waitForJobCompletion(jobId: string, timeoutMs: number = 30000): Promise<any> {
    const startTime = Date.now();
    
    while (Date.now() - startTime < timeoutMs) {
      const status = await this.getJobStatus(jobId);
      
      if (status.status === 'completed') {
        return status;
      } else if (status.status === 'failed') {
        throw new Error(`Job failed: ${status.error || 'Unknown error'}`);
      }
      
      await new Promise(resolve => setTimeout(resolve, 1000));
    }
    
    throw new Error(`Job timeout after ${timeoutMs}ms`);
  }

  async exportDeck(deckData: any, format: string): Promise<string> {
    const response = await this.request.post(`${this.baseURL}/api/export/${format}`, {
      data: deckData
    });

    if (!response.ok()) {
      throw new Error(`Export failed: ${response.status()}`);
    }

    return await response.text();
  }

  async checkHealth(): Promise<any> {
    const response = await this.request.get(`${this.baseURL}/health`);
    return await response.json();
  }
}
import axios, { AxiosInstance } from 'axios';
import FormData from 'form-data';
import { config } from './config';
import { logger } from './logger';

export interface OCRResult {
  jobId: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  result?: {
    mainboard: Array<{ qty: number; name: string }>;
    sideboard: Array<{ qty: number; name: string }>;
    metadata?: {
      confidence: number;
      processingTime: number;
      usedVisionFallback: boolean;
    };
  };
  error?: string;
}

export interface ExportRequest {
  format: 'mtga' | 'moxfield' | 'archidekt' | 'tappedout';
  mainboard: Array<{ qty: number; name: string }>;
  sideboard?: Array<{ qty: number; name: string }>;
  deckName?: string;
}

export class Screen2DeckAPIClient {
  private client: AxiosInstance;
  
  constructor() {
    this.client = axios.create({
      baseURL: config.apiUrl,
      headers: {
        ...(config.apiKey && { 'X-API-Key': config.apiKey })
      },
      timeout: 30000  // 30 seconds
    });
    
    // Add request/response interceptors for logging
    this.client.interceptors.request.use(
      (request) => {
        logger.debug('API Request', {
          method: request.method,
          url: request.url,
          headers: request.headers
        });
        return request;
      },
      (error) => {
        logger.error('API Request Error', error);
        return Promise.reject(error);
      }
    );
    
    this.client.interceptors.response.use(
      (response) => {
        logger.debug('API Response', {
          status: response.status,
          url: response.config.url
        });
        return response;
      },
      (error) => {
        logger.error('API Response Error', {
          status: error.response?.status,
          data: error.response?.data,
          url: error.config?.url
        });
        return Promise.reject(error);
      }
    );
  }
  
  async uploadImage(imageBuffer: Buffer, filename: string): Promise<string> {
    const formData = new FormData();
    formData.append('file', imageBuffer, {
      filename,
      contentType: 'image/png'
    });
    
    const response = await this.client.post<{ jobId: string }>('/api/ocr/upload', formData, {
      headers: {
        ...formData.getHeaders()
      }
    });
    
    return response.data.jobId;
  }
  
  async checkStatus(jobId: string): Promise<OCRResult> {
    const response = await this.client.get<OCRResult>(`/api/ocr/status/${jobId}`);
    return response.data;
  }
  
  async waitForCompletion(jobId: string, maxWaitMs: number = 30000): Promise<OCRResult> {
    const startTime = Date.now();
    const pollInterval = 1000;  // 1 second
    
    while (Date.now() - startTime < maxWaitMs) {
      const result = await this.checkStatus(jobId);
      
      if (result.status === 'completed' || result.status === 'failed') {
        return result;
      }
      
      await new Promise(resolve => setTimeout(resolve, pollInterval));
    }
    
    throw new Error(`OCR job ${jobId} timed out after ${maxWaitMs}ms`);
  }
  
  async exportDeck(request: ExportRequest): Promise<string> {
    const response = await this.client.post<{ content: string }>(
      `/api/export/${request.format}`,
      {
        mainboard: request.mainboard,
        sideboard: request.sideboard,
        deckName: request.deckName
      }
    );
    
    return response.data.content;
  }
  
  async health(): Promise<boolean> {
    try {
      const response = await this.client.get('/health');
      return response.status === 200;
    } catch {
      return false;
    }
  }
}
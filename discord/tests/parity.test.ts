import { describe, it, expect, beforeAll, afterAll } from '@jest/globals';
import { Screen2DeckAPIClient } from '../src/api-client';
import fs from 'fs/promises';
import path from 'path';

/**
 * Parity Tests
 * 
 * These tests ensure that the Discord bot produces identical results
 * to the web application using the same golden test data.
 */

describe('Discord ↔️ Web Parity Tests', () => {
  let apiClient: Screen2DeckAPIClient;
  let goldenData: any[];
  
  beforeAll(async () => {
    apiClient = new Screen2DeckAPIClient();
    
    // Load golden test data
    const goldenDir = path.join(__dirname, '../../validation_set/golden');
    const files = await fs.readdir(goldenDir);
    
    goldenData = await Promise.all(
      files
        .filter(f => f.endsWith('.json'))
        .map(async (file) => {
          const content = await fs.readFile(path.join(goldenDir, file), 'utf-8');
          return JSON.parse(content);
        })
    );
  });
  
  describe('OCR Processing', () => {
    it('should achieve ≥95% accuracy on test images', async () => {
      const testImage = await fs.readFile(
        path.join(__dirname, '../../validation_set/test_deck_1.jpg')
      );
      
      // Upload and process
      const jobId = await apiClient.uploadImage(testImage, 'test_deck_1.jpg');
      const result = await apiClient.waitForCompletion(jobId);
      
      expect(result.status).toBe('completed');
      expect(result.result).toBeDefined();
      
      // Compare with golden data
      const golden = goldenData[0];
      const accuracy = calculateAccuracy(result.result!, golden);
      
      expect(accuracy).toBeGreaterThanOrEqual(0.95);
    });
    
    it('should process within 5 seconds P95', async () => {
      const testImage = await fs.readFile(
        path.join(__dirname, '../../validation_set/test_deck_2.jpg')
      );
      
      const startTime = Date.now();
      const jobId = await apiClient.uploadImage(testImage, 'test_deck_2.jpg');
      const result = await apiClient.waitForCompletion(jobId);
      const processingTime = Date.now() - startTime;
      
      expect(result.status).toBe('completed');
      expect(processingTime).toBeLessThan(5000);
    });
    
    it('should handle sideboard correctly', async () => {
      const testImage = await fs.readFile(
        path.join(__dirname, '../../validation_set/test_deck_with_sideboard.jpg')
      );
      
      const jobId = await apiClient.uploadImage(testImage, 'test_deck_with_sideboard.jpg');
      const result = await apiClient.waitForCompletion(jobId);
      
      expect(result.status).toBe('completed');
      expect(result.result?.sideboard).toBeDefined();
      expect(result.result?.sideboard.length).toBeGreaterThan(0);
    });
  });
  
  describe('Export Format Parity', () => {
    const testDeck = {
      mainboard: [
        { qty: 4, name: 'Lightning Bolt' },
        { qty: 4, name: 'Counterspell' },
        { qty: 24, name: 'Island' },
        { qty: 10, name: 'Mountain' }
      ],
      sideboard: [
        { qty: 3, name: 'Blood Moon' },
        { qty: 2, name: 'Surgical Extraction' }
      ]
    };
    
    it('should export MTGA format correctly', async () => {
      const exported = await apiClient.exportDeck({
        format: 'mtga',
        mainboard: testDeck.mainboard,
        sideboard: testDeck.sideboard
      });
      
      expect(exported).toContain('4 Lightning Bolt');
      expect(exported).toContain('4 Counterspell');
      expect(exported).toContain('\n\n');  // Sideboard separator
      expect(exported).toContain('3 Blood Moon');
    });
    
    it('should export Moxfield format correctly', async () => {
      const exported = await apiClient.exportDeck({
        format: 'moxfield',
        mainboard: testDeck.mainboard,
        sideboard: testDeck.sideboard
      });
      
      expect(exported).toContain('4x Lightning Bolt');
      expect(exported).toContain('4x Counterspell');
      expect(exported).toContain('Sideboard:');
      expect(exported).toContain('3x Blood Moon');
    });
    
    it('should export Archidekt format correctly', async () => {
      const exported = await apiClient.exportDeck({
        format: 'archidekt',
        mainboard: testDeck.mainboard,
        sideboard: testDeck.sideboard
      });
      
      expect(exported).toContain('4 Lightning Bolt');
      expect(exported).toContain('4 Counterspell');
      expect(exported).toContain('Sideboard');
      expect(exported).toContain('3 Blood Moon');
    });
    
    it('should export TappedOut format correctly', async () => {
      const exported = await apiClient.exportDeck({
        format: 'tappedout',
        mainboard: testDeck.mainboard,
        sideboard: testDeck.sideboard
      });
      
      expect(exported).toContain('4x Lightning Bolt');
      expect(exported).toContain('4x Counterspell');
      expect(exported).toContain('Sideboard:');
      expect(exported).toContain('3x Blood Moon');
    });
  });
  
  describe('Error Handling Parity', () => {
    it('should handle invalid image format', async () => {
      const invalidFile = Buffer.from('not an image');
      
      await expect(
        apiClient.uploadImage(invalidFile, 'test.txt')
      ).rejects.toThrow();
    });
    
    it('should handle oversized images', async () => {
      // Create a fake 10MB buffer
      const oversizedImage = Buffer.alloc(10 * 1024 * 1024);
      
      await expect(
        apiClient.uploadImage(oversizedImage, 'large.jpg')
      ).rejects.toThrow();
    });
    
    it('should handle API timeout gracefully', async () => {
      // Use a non-existent job ID
      await expect(
        apiClient.waitForCompletion('non-existent-job', 1000)
      ).rejects.toThrow(/timed out/);
    });
  });
  
  describe('Cache Behavior', () => {
    it('should return cached results for identical images', async () => {
      const testImage = await fs.readFile(
        path.join(__dirname, '../../validation_set/test_deck_1.jpg')
      );
      
      // First request
      const jobId1 = await apiClient.uploadImage(testImage, 'test_deck_1.jpg');
      const result1 = await apiClient.waitForCompletion(jobId1);
      
      // Second request with same image
      const jobId2 = await apiClient.uploadImage(testImage, 'test_deck_1.jpg');
      const result2 = await apiClient.waitForCompletion(jobId2);
      
      // Should be faster due to caching
      expect(result2.result).toEqual(result1.result);
    });
  });
  
  describe('Metadata Consistency', () => {
    it('should provide consistent metadata', async () => {
      const testImage = await fs.readFile(
        path.join(__dirname, '../../validation_set/test_deck_1.jpg')
      );
      
      const jobId = await apiClient.uploadImage(testImage, 'test_deck_1.jpg');
      const result = await apiClient.waitForCompletion(jobId);
      
      expect(result.result?.metadata).toBeDefined();
      expect(result.result?.metadata?.confidence).toBeGreaterThan(0);
      expect(result.result?.metadata?.confidence).toBeLessThanOrEqual(1);
      expect(result.result?.metadata?.processingTime).toBeGreaterThan(0);
      expect(typeof result.result?.metadata?.usedVisionFallback).toBe('boolean');
    });
  });
});

// Helper function to calculate accuracy
function calculateAccuracy(actual: any, expected: any): number {
  const actualCards = new Map<string, number>();
  const expectedCards = new Map<string, number>();
  
  // Build maps
  [...actual.mainboard, ...(actual.sideboard || [])].forEach((card: any) => {
    actualCards.set(card.name.toLowerCase(), card.qty);
  });
  
  [...expected.mainboard, ...(expected.sideboard || [])].forEach((card: any) => {
    expectedCards.set(card.name.toLowerCase(), card.qty);
  });
  
  // Calculate matches
  let matches = 0;
  let total = 0;
  
  expectedCards.forEach((qty, name) => {
    total += qty;
    const actualQty = actualCards.get(name) || 0;
    matches += Math.min(qty, actualQty);
  });
  
  return total > 0 ? matches / total : 0;
}
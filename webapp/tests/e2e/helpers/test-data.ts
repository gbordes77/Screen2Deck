import path from 'path';

/**
 * Test Data Management
 * Handles test images and expected results
 */
export class TestData {
  static readonly VALIDATION_SET_DIR = process.env.DATASET_DIR || './validation_set';
  static readonly GOLDEN_DIR = process.env.GOLDEN_DIR || './validation_set/golden';

  static getImagePath(imageName: string): string {
    return path.join(TestData.VALIDATION_SET_DIR, imageName);
  }

  static getGoldenPath(imageName: string, format?: string): string {
    if (format) {
      return path.join(TestData.GOLDEN_DIR, 'exports', imageName.replace(/\.[^.]+$/, ''), `${format}.txt`);
    }
    return path.join(TestData.GOLDEN_DIR, imageName.replace(/\.[^.]+$/, '.json'));
  }

  static async loadGolden(imageName: string): Promise<any> {
    const fs = await import('fs/promises');
    try {
      const goldenPath = TestData.getGoldenPath(imageName);
      const content = await fs.readFile(goldenPath, 'utf-8');
      return JSON.parse(content);
    } catch (error) {
      console.warn(`Could not load golden data for ${imageName}:`, error);
      return null;
    }
  }

  static async loadGoldenExport(imageName: string, format: string): Promise<string | null> {
    const fs = await import('fs/promises');
    try {
      const exportPath = TestData.getGoldenPath(imageName, format);
      return await fs.readFile(exportPath, 'utf-8');
    } catch (error) {
      console.warn(`Could not load golden export for ${imageName} (${format}):`, error);
      return null;
    }
  }

  // Common test images from the validation set
  static readonly TEST_IMAGES = {
    MTGA_DECK_1: 'MTGA deck list_1535x728.jpeg',
    MTGA_DECK_4: 'MTGA deck list 4_1920x1080.jpeg',
    MTGO_USUAL: 'MTGO deck list usual_1763x791.jpeg',
    MTGO_UNUSUAL: 'MTGO deck list not usual_2336x1098.jpeg',
    GOLDFISH: 'mtggoldfish deck list 10_1239x1362.jpg',
    WEB_DECK: 'web site  deck list_2300x2210.jpeg',
    REAL_CARDS: 'real deck cartes cachés_2048x1542.jpeg',
    WEBP_IMAGE: 'image_677x309.webp'
  };

  static getAllTestImages(): string[] {
    return Object.values(TestData.TEST_IMAGES);
  }
}
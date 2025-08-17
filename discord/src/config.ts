import dotenv from 'dotenv';
import { join } from 'path';

// Load environment variables
dotenv.config({ path: join(__dirname, '..', '.env') });

export interface Config {
  // Discord
  discordToken: string;
  clientId: string;
  guildId?: string;  // Optional for development
  
  // Screen2Deck API
  apiUrl: string;
  apiKey?: string;
  
  // Bot Settings
  nodeEnv: 'development' | 'production' | 'test';
  logLevel: 'error' | 'warn' | 'info' | 'debug';
  cacheTTL: number;
  
  // Feature Flags
  enableVisionFallback: boolean;
  enableMetrics: boolean;
  
  // Rate Limiting
  maxConcurrentJobs: number;
  rateLimitPerUser: number;
  rateLimitWindowMinutes: number;
}

function requireEnv(key: string): string {
  const value = process.env[key];
  if (!value) {
    throw new Error(`Missing required environment variable: ${key}`);
  }
  return value;
}

function getConfig(): Config {
  return {
    // Discord
    discordToken: requireEnv('DISCORD_TOKEN'),
    clientId: requireEnv('DISCORD_CLIENT_ID'),
    guildId: process.env.DISCORD_GUILD_ID,
    
    // Screen2Deck API
    apiUrl: process.env.SCREEN2DECK_API_URL || 'http://localhost:8080',
    apiKey: process.env.SCREEN2DECK_API_KEY,
    
    // Bot Settings
    nodeEnv: (process.env.NODE_ENV as Config['nodeEnv']) || 'development',
    logLevel: (process.env.LOG_LEVEL as Config['logLevel']) || 'info',
    cacheTTL: parseInt(process.env.CACHE_TTL || '3600', 10),
    
    // Feature Flags
    enableVisionFallback: process.env.ENABLE_VISION_FALLBACK === 'true',
    enableMetrics: process.env.ENABLE_METRICS !== 'false',
    
    // Rate Limiting
    maxConcurrentJobs: parseInt(process.env.MAX_CONCURRENT_JOBS || '5', 10),
    rateLimitPerUser: parseInt(process.env.RATE_LIMIT_PER_USER || '10', 10),
    rateLimitWindowMinutes: parseInt(process.env.RATE_LIMIT_WINDOW_MINUTES || '60', 10),
  };
}

export const config = getConfig();
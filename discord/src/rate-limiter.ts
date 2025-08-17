import { config } from './config';
import { logger } from './logger';

interface UserRateLimit {
  count: number;
  resetTime: number;
}

export class RateLimiter {
  private limits: Map<string, UserRateLimit> = new Map();
  private readonly maxRequests: number;
  private readonly windowMs: number;
  
  constructor() {
    this.maxRequests = config.rateLimitPerUser;
    this.windowMs = config.rateLimitWindowMinutes * 60 * 1000;
    
    // Clean up old entries every minute
    setInterval(() => this.cleanup(), 60000);
  }
  
  checkLimit(userId: string): boolean {
    const now = Date.now();
    const userLimit = this.limits.get(userId);
    
    if (!userLimit || now > userLimit.resetTime) {
      // Create new limit window
      this.limits.set(userId, {
        count: 1,
        resetTime: now + this.windowMs
      });
      return true;
    }
    
    if (userLimit.count >= this.maxRequests) {
      logger.warn('Rate limit exceeded', { 
        userId,
        count: userLimit.count,
        resetIn: userLimit.resetTime - now
      });
      return false;
    }
    
    // Increment count
    userLimit.count++;
    return true;
  }
  
  getRemainingRequests(userId: string): number {
    const userLimit = this.limits.get(userId);
    if (!userLimit || Date.now() > userLimit.resetTime) {
      return this.maxRequests;
    }
    return Math.max(0, this.maxRequests - userLimit.count);
  }
  
  getResetTime(userId: string): number | null {
    const userLimit = this.limits.get(userId);
    if (!userLimit || Date.now() > userLimit.resetTime) {
      return null;
    }
    return userLimit.resetTime;
  }
  
  private cleanup() {
    const now = Date.now();
    for (const [userId, limit] of this.limits.entries()) {
      if (now > limit.resetTime) {
        this.limits.delete(userId);
      }
    }
  }
}
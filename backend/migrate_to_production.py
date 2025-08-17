#!/usr/bin/env python3
"""
Migration script to update main.py to production-ready version.
Run this script to apply all security and architecture improvements.
"""

import shutil
import os
from pathlib import Path

def migrate():
    """Migrate to production-ready main.py"""
    
    print("🚀 Starting migration to production-ready Screen2Deck API...")
    
    # Backup original main.py
    main_path = Path("app/main.py")
    backup_path = Path("app/main_original.py")
    
    if main_path.exists():
        print(f"📦 Backing up original main.py to {backup_path}")
        shutil.copy2(main_path, backup_path)
    
    # Replace with refactored version
    refactored_path = Path("app/main_refactored.py")
    if refactored_path.exists():
        print(f"✨ Replacing main.py with production-ready version")
        shutil.copy2(refactored_path, main_path)
        print("✅ main.py updated successfully")
    else:
        print("❌ Refactored main.py not found")
        return False
    
    # Create .env file if not exists
    env_path = Path(".env")
    if not env_path.exists():
        print("📝 Creating .env file with secure defaults")
        import secrets
        jwt_secret = secrets.token_urlsafe(32)
        
        env_content = f"""# Screen2Deck Production Configuration

# Application
APP_ENV=production
PORT=8080
LOG_LEVEL=INFO
DEBUG=false

# Security (CHANGE THESE!)
JWT_SECRET_KEY={jwt_secret}
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# Database (configure for production)
DATABASE_URL=postgresql://screen2deck:password@localhost:5432/screen2deck

# Redis
REDIS_URL=redis://localhost:6379/0
USE_REDIS=true

# OCR
ENABLE_VISION_FALLBACK=false
OPENAI_API_KEY=your-openai-api-key-here
MAX_IMAGE_MB=10

# CORS (update for your domain)
CORS_ORIGINS=["http://localhost:3000","https://screen2deck.com"]

# Rate Limiting
RATE_LIMIT_ENABLED=true
RATE_LIMIT_PER_MINUTE=30

# Monitoring
ENABLE_METRICS=true
ENABLE_TRACING=false
"""
        
        with open(env_path, "w") as f:
            f.write(env_content)
        print("✅ .env file created")
    
    # Update requirements.txt
    requirements_path = Path("requirements.txt")
    additional_deps = [
        "python-magic==0.4.27",
        "psutil==5.9.8",
        "prometheus-client==0.19.0"
    ]
    
    if requirements_path.exists():
        print("📦 Updating requirements.txt")
        with open(requirements_path, "r") as f:
            current_deps = f.read()
        
        for dep in additional_deps:
            if dep.split("==")[0] not in current_deps:
                current_deps += f"\n{dep}"
        
        with open(requirements_path, "w") as f:
            f.write(current_deps.strip() + "\n")
        print("✅ requirements.txt updated")
    
    print("\n" + "="*60)
    print("✅ MIGRATION COMPLETE!")
    print("="*60)
    print("""
Next steps:
1. Review and update .env file with your production settings
2. Install new dependencies: pip install -r requirements.txt
3. Set up PostgreSQL and Redis if not already configured
4. Run database migrations if using PostgreSQL
5. Test the application: python -m app.main
6. Deploy to production!

Security checklist:
☐ Change JWT_SECRET_KEY in .env
☐ Configure DATABASE_URL with strong password
☐ Set up Redis with authentication
☐ Update CORS_ORIGINS for your domain
☐ Configure HTTPS in production
☐ Set up monitoring and alerting
☐ Review rate limiting settings
☐ Enable OpenTelemetry tracing
""")
    
    return True

if __name__ == "__main__":
    success = migrate()
    exit(0 if success else 1)
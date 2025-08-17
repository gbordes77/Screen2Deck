#!/bin/bash

echo "🔍 Checking Docker status..."

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running!"
    echo "👉 Please start Docker Desktop manually"
    
    # Try to start Docker Desktop on macOS
    if [[ "$OSTYPE" == "darwin"* ]]; then
        echo "🚀 Attempting to start Docker Desktop..."
        open -a Docker
        echo "⏳ Waiting for Docker to start (this may take 30-60 seconds)..."
        
        # Wait for Docker to be ready
        for i in {1..60}; do
            if docker info > /dev/null 2>&1; then
                echo "✅ Docker is now running!"
                break
            fi
            echo -n "."
            sleep 1
        done
        
        if ! docker info > /dev/null 2>&1; then
            echo ""
            echo "❌ Docker failed to start after 60 seconds"
            echo "Please start Docker Desktop manually and try again"
            exit 1
        fi
    else
        echo "Please start Docker and try again"
        exit 1
    fi
fi

echo "✅ Docker is running"

# Check if services are already running
echo ""
echo "🔍 Checking existing containers..."
if docker ps | grep -q "screen2deck"; then
    echo "⚠️ Screen2Deck containers are already running"
    echo "Would you like to restart them? (y/n)"
    read -r response
    if [[ "$response" == "y" ]]; then
        echo "🔄 Stopping existing containers..."
        docker compose down
        sleep 2
    else
        echo "Using existing containers"
        exit 0
    fi
fi

# Start services
echo ""
echo "🚀 Starting Screen2Deck services..."
docker compose up -d

# Wait for services to be ready
echo ""
echo "⏳ Waiting for services to be ready..."
sleep 5

# Check service health
echo ""
echo "🏥 Checking service health..."

# Check backend
if curl -s http://localhost:8080/health > /dev/null; then
    echo "✅ Backend API is healthy (port 8080)"
else
    echo "❌ Backend API is not responding on port 8080"
fi

# Check frontend
if curl -s http://localhost:3000 > /dev/null; then
    echo "✅ Frontend is healthy (port 3000)"
else
    echo "❌ Frontend is not responding on port 3000"
fi

# Check Redis
if docker exec $(docker ps -q -f name=redis) redis-cli ping > /dev/null 2>&1; then
    echo "✅ Redis is healthy (port 6379)"
else
    echo "⚠️ Redis might not be responding (this is okay for basic tests)"
fi

echo ""
echo "🎉 Services are ready for E2E testing!"
echo "Run: ./run-e2e-tests.sh to start testing"
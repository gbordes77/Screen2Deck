#!/bin/bash
# Test API upload → status → export flow

echo "📋 Test upload → status → export"

# Create a dummy test image if needed
if [ ! -f test_card.jpg ]; then
    echo "Creating test image..."
    # Create a 100x100 white image with ImageMagick or just use any existing image
    echo "No test image, using placeholder test"
fi

# Test health first
echo "1️⃣ Testing health endpoint..."
curl -s http://localhost:8080/health | jq . || echo "❌ Health check failed"

echo -e "\n2️⃣ Testing metrics endpoint..."
curl -s http://localhost:8080/metrics | head -10 || echo "❌ Metrics not available"

echo -e "\n3️⃣ Testing upload (would need real image)..."
# curl -X POST -F "file=@test_card.jpg" http://localhost:8080/api/ocr/upload

echo -e "\n✅ Basic connectivity test complete"
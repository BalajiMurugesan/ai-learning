#!/bin/bash

BASE_URL="http://localhost:8000"

echo "=== 1. Testing Health Check ==="
curl -s -X GET "$BASE_URL/health"
echo -e "\n\n"

echo "=== 2. Testing Standard POST Generation ==="
curl -s -X POST "$BASE_URL/generate/post" \
     -H "Content-Type: application/json" \
     -d '{ "query": "What is 2+2?" }'
echo -e "\n\n"

echo "=== 3. Testing POST Streaming with Telemetry ==="
curl -N -s -X POST "$BASE_URL/generate/post?stream=true" \
     -H "Content-Type: application/json" \
     -d '{ "query": "Say hello in 3 languages." }'
echo -e "\n\n"

echo "=== 4. Testing Pydantic Validation Error (Extra Field) ==="
curl -s -X POST "$BASE_URL/generate/post" \
     -H "Content-Type: application/json" \
     -d '{ "invalid_field": "test" }'
echo -e "\n"
#!/bin/bash
# Demo script for Transparent News Assistant

API_URL="http://localhost:8000"

echo "=== Transparent News Assistant Demo ==="
echo ""

# Check if API is running
echo "1. Checking API health..."
curl -s "$API_URL/health" | jq .
echo ""

# Ingest sample data
echo "2. Ingesting sample RSS feed..."
INGEST_RESPONSE=$(curl -s -X POST "$API_URL/ingest/rss" \
  -H "Content-Type: application/json" \
  -d '{
    "feed_url": "https://feeds.yle.fi/uutiset/v1/recent.rss?publisherIds=YLE_UUTISET",
    "publisher": "Yle",
    "limit": 10
  }')
echo "$INGEST_RESPONSE" | jq .
echo ""

# Wait a bit for indexing
echo "3. Waiting for indexing to complete..."
sleep 3
echo ""

# Scenario 1: Basic question
echo "=== Scenario 1: Basic Question ==="
echo "Question: Mitä uutisia on tänään?"
RESPONSE1=$(curl -s -X POST "$API_URL/chat" \
  -H "Content-Type: application/json" \
  -d '{"question": "Mitä uutisia on tänään?"}')
echo "$RESPONSE1" | jq -r '.answer'
echo ""
echo "Sources:"
echo "$RESPONSE1" | jq -r '.sources[] | "\(.label): \(.title) - \(.url)"'
echo ""

# Scenario 2: Specific topic
echo "=== Scenario 2: Specific Topic ==="
echo "Question: Kerro viimeisimmistä teknologiauutisista"
RESPONSE2=$(curl -s -X POST "$API_URL/chat" \
  -H "Content-Type: application/json" \
  -d '{"question": "Kerro viimeisimmistä teknologiauutisista"}')
echo "$RESPONSE2" | jq -r '.answer'
echo ""
if [ "$(echo "$RESPONSE2" | jq -r '.warnings | length')" -gt 0 ]; then
  echo "Warnings:"
  echo "$RESPONSE2" | jq -r '.warnings[]'
fi
echo ""

# Scenario 3: Insufficient sources
echo "=== Scenario 3: Insufficient Sources ==="
echo "Question: Mitä tapahtui vuonna 1800?"
RESPONSE3=$(curl -s -X POST "$API_URL/chat" \
  -H "Content-Type: application/json" \
  -d '{"question": "Mitä tapahtui vuonna 1800?"}')
echo "$RESPONSE3" | jq -r '.answer'
echo ""

# Show audit trail
echo "=== Audit Trail (Last 5 Runs) ==="
curl -s "$API_URL/runs?limit=5" | jq '.[] | {id, question, created_at}'
echo ""

echo "=== Demo Complete ==="

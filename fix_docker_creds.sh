#!/bin/bash
# Fix Docker credential helper issues on Linux/WSL

set -e

echo "Fixing Docker credential helper issues..."

DOCKER_CONFIG="${DOCKER_CONFIG:-$HOME/.docker/config.json}"
BACKUP_FILE="${DOCKER_CONFIG}.backup.$(date +%Y%m%d_%H%M%S)"

# Check if config exists
if [ -f "$DOCKER_CONFIG" ]; then
    echo "Backing up Docker config to: $BACKUP_FILE"
    cp "$DOCKER_CONFIG" "$BACKUP_FILE"
    
    # Remove credential helper from config
    echo "Removing credential helper from Docker config..."
    if command -v jq &> /dev/null; then
        # Use jq if available (cleaner)
        jq 'del(.credsStore) | del(.credHelpers)' "$DOCKER_CONFIG" > "${DOCKER_CONFIG}.tmp" && \
        mv "${DOCKER_CONFIG}.tmp" "$DOCKER_CONFIG"
    else
        # Fallback: use sed to remove credential helper lines
        sed -i.bak '/"credsStore"/d; /"credHelpers"/d' "$DOCKER_CONFIG"
        rm -f "${DOCKER_CONFIG}.bak"
    fi
    echo "✓ Docker config updated"
else
    echo "Creating new Docker config without credential helper..."
    mkdir -p "$(dirname "$DOCKER_CONFIG")"
    echo '{}' > "$DOCKER_CONFIG"
fi

# Test Docker access
echo ""
echo "Testing Docker access..."
if docker pull hello-world:latest > /dev/null 2>&1; then
    docker rmi hello-world:latest > /dev/null 2>&1 || true
    echo "✓ Docker is working correctly!"
    echo ""
    echo "You can now run: make build"
else
    echo "⚠ Docker pull still has issues. Try:"
    echo "  1. Restart Docker Desktop"
    echo "  2. Check if Docker is running: docker info"
fi

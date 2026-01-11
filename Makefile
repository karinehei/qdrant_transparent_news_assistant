.PHONY: up down build test lint format clean ingest demo

# Start all services
up:
	docker-compose up -d

# Stop all services
down:
	docker-compose down

# Build containers
build:
	@echo "Checking Docker availability..."
	@docker info > /dev/null 2>&1 || (echo "Error: Docker is not running or not accessible. Please start Docker Desktop." && exit 1)
	@echo "Attempting to pull base image..."
	@docker pull python:3.11-slim > /dev/null 2>&1 || echo "Note: Will pull during build if needed"
	@echo "Building containers..."
	@DOCKER_BUILDKIT=0 docker-compose build || \
		(echo "Legacy builder failed, trying BuildKit..." && \
		 DOCKER_BUILDKIT=1 COMPOSE_DOCKER_CLI_BUILD=1 docker-compose build)

# Run tests
test:
	pytest tests/ -v

# Lint code
lint:
	ruff check news_assistant/
	mypy news_assistant/

# Format code
format:
	black news_assistant/ tests/
	ruff check --fix news_assistant/ tests/

# Clean up
clean:
	docker-compose down -v
	find . -type d -name __pycache__ -exec rm -r {} +
	find . -type f -name "*.pyc" -delete

# Ingest sample RSS feed
ingest:
	@echo "Ingesting RSS feed..."
	@curl -X POST http://localhost:8000/ingest/rss \
		-H "Content-Type: application/json" \
		-d '{"feed_url": "https://feeds.yle.fi/uutiset/v1/recent.rss?publisherIds=YLE_UUTISET", "publisher": "Yle", "limit": 10}' || \
		powershell -Command "$$body = @{feed_url='https://feeds.yle.fi/uutiset/v1/recent.rss?publisherIds=YLE_UUTISET'; publisher='Yle'; limit=10} | ConvertTo-Json; Invoke-RestMethod -Uri 'http://localhost:8000/ingest/rss' -Method Post -Body $$body -ContentType 'application/json'"

# Run demo chat
demo:
	@echo "Demo: Asking about recent news"
	@curl -X POST http://localhost:8000/chat \
		-H "Content-Type: application/json" \
		-d '{"question": "Mitä uutisia on tänään?"}' || \
		powershell -Command "$$body = @{question='Mitä uutisia on tänään?'} | ConvertTo-Json; Invoke-RestMethod -Uri 'http://localhost:8000/chat' -Method Post -Body $$body -ContentType 'application/json' | ConvertTo-Json -Depth 10"

# Initialize database
init-db:
	docker-compose exec api python -c "from news_assistant.audit_db import get_engine, init_db; from news_assistant.settings import settings; engine = get_engine(settings.audit_db_url); init_db(engine)"

# Run migrations (when Alembic is set up)
migrate:
	docker-compose exec api alembic upgrade head

# Fix Docker credential issues (run this if build fails with credential errors)
fix-docker-creds:
	@echo "Fixing Docker credential helper issues..."
	@if [ -f "./fix_docker_creds.sh" ]; then \
		bash ./fix_docker_creds.sh; \
	else \
		echo "Running manual fix..."; \
		DOCKER_CONFIG=$${DOCKER_CONFIG:-$$HOME/.docker/config.json}; \
		if [ -f "$$DOCKER_CONFIG" ]; then \
			echo "Backing up Docker config..."; \
			cp "$$DOCKER_CONFIG" "$${DOCKER_CONFIG}.backup.$$(date +%Y%m%d_%H%M%S)"; \
			echo "Removing credential helper from config..."; \
			if command -v jq &> /dev/null; then \
				jq 'del(.credsStore) | del(.credHelpers)' "$$DOCKER_CONFIG" > "$${DOCKER_CONFIG}.tmp" && \
				mv "$${DOCKER_CONFIG}.tmp" "$$DOCKER_CONFIG"; \
			else \
				sed -i.bak '/"credsStore"/d; /"credHelpers"/d' "$$DOCKER_CONFIG" && rm -f "$${DOCKER_CONFIG}.bak"; \
			fi; \
			echo "✓ Docker config updated"; \
		else \
			echo "Creating new Docker config..."; \
			mkdir -p $$(dirname "$$DOCKER_CONFIG"); \
			echo '{}' > "$$DOCKER_CONFIG"; \
		fi; \
		echo ""; \
		echo "Testing Docker access..."; \
		docker pull hello-world:latest > /dev/null 2>&1 && \
			(docker rmi hello-world:latest > /dev/null 2>&1 || true) && \
			echo "✓ Docker is working correctly!" || \
			echo "⚠ Docker test failed. Try restarting Docker Desktop."; \
	fi
	@echo ""
	@echo "You can now run: make build"

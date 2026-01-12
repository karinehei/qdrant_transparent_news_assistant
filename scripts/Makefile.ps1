# PowerShell-compatible Makefile alternative
# Usage: .\Makefile.ps1 <target>

param(
    [Parameter(Mandatory=$true)]
    [string]$Target
)

$ErrorActionPreference = "Stop"

switch ($Target) {
    "up" {
        docker-compose up -d
    }
    "down" {
        docker-compose down
    }
    "build" {
        Write-Host "Checking Docker availability..."
        docker info | Out-Null
        if ($LASTEXITCODE -ne 0) {
            Write-Host "Error: Docker is not running or not accessible. Please start Docker Desktop." -ForegroundColor Red
            exit 1
        }
        Write-Host "Attempting to pull base image..."
        docker pull python:3.11-slim 2>&1 | Out-Null
        if ($LASTEXITCODE -ne 0) {
            Write-Host "Note: Will pull during build if needed" -ForegroundColor Yellow
        }
        Write-Host "Building containers..."
        $env:DOCKER_BUILDKIT = "0"
        docker-compose build
        if ($LASTEXITCODE -ne 0) {
            Write-Host "Legacy builder failed, trying BuildKit..." -ForegroundColor Yellow
            $env:DOCKER_BUILDKIT = "1"
            $env:COMPOSE_DOCKER_CLI_BUILD = "1"
            docker-compose build
        }
    }
    "test" {
        pytest tests/ -v
    }
    "lint" {
        ruff check news_assistant/
        mypy news_assistant/
    }
    "format" {
        black news_assistant/ tests/
        ruff check --fix news_assistant/ tests/
    }
    "clean" {
        docker-compose down -v
        Get-ChildItem -Recurse -Directory -Filter __pycache__ | Remove-Item -Recurse -Force
        Get-ChildItem -Recurse -Filter *.pyc | Remove-Item -Force
    }
    "ingest" {
        $body = @{
            feed_url = "https://feeds.yle.fi/uutiset/v1/recent.rss?publisherIds=YLE_UUTISET"
            publisher = "Yle"
            limit = 10
        } | ConvertTo-Json
        Invoke-RestMethod -Uri "http://localhost:8000/ingest/rss" -Method Post -Body $body -ContentType "application/json"
    }
    "demo" {
        Write-Host "Demo: Asking about recent news"
        $body = @{
            question = "Mitä uutisia on tänään?"
        } | ConvertTo-Json
        Invoke-RestMethod -Uri "http://localhost:8000/chat" -Method Post -Body $body -ContentType "application/json" | ConvertTo-Json -Depth 10
    }
    "init-db" {
        docker-compose exec api python -c "from news_assistant.audit_db import get_engine, init_db; from news_assistant.settings import settings; engine = get_engine(settings.audit_db_url); init_db(engine)"
    }
    "migrate" {
        docker-compose exec api alembic upgrade head
    }
    "fix-docker-creds" {
        Write-Host "Fixing Docker credential helper issues..." -ForegroundColor Cyan
        if (Test-Path ".\fix_docker_creds.ps1") {
            & ".\fix_docker_creds.ps1"
        } else {
            Write-Host "Running manual fix..." -ForegroundColor Yellow
            $dockerConfig = if ($env:DOCKER_CONFIG) { $env:DOCKER_CONFIG } else { "$env:USERPROFILE\.docker\config.json" }
            $backupFile = "${dockerConfig}.backup.$(Get-Date -Format 'yyyyMMdd_HHmmss')"
            
            if (Test-Path $dockerConfig) {
                Write-Host "Backing up Docker config to: $backupFile"
                Copy-Item $dockerConfig $backupFile
                
                try {
                    $config = Get-Content $dockerConfig -Raw | ConvertFrom-Json
                    $modified = $false
                    if ($config.PSObject.Properties.Name -contains 'credsStore') {
                        $config.PSObject.Properties.Remove('credsStore')
                        $modified = $true
                    }
                    if ($config.PSObject.Properties.Name -contains 'credHelpers') {
                        $config.PSObject.Properties.Remove('credHelpers')
                        $modified = $true
                    }
                    if ($modified) {
                        $config | ConvertTo-Json -Depth 10 | Set-Content $dockerConfig
                        Write-Host "✓ Docker config updated" -ForegroundColor Green
                    } else {
                        Write-Host "✓ No credential helper found in config" -ForegroundColor Green
                    }
                } catch {
                    Write-Host "Error modifying config, trying alternative method..." -ForegroundColor Yellow
                    $content = Get-Content $dockerConfig
                    $content | Where-Object { $_ -notmatch '"credsStore"' -and $_ -notmatch '"credHelpers"' } | Set-Content "${dockerConfig}.tmp"
                    Move-Item -Force "${dockerConfig}.tmp" $dockerConfig
                    Write-Host "✓ Docker config updated (fallback method)" -ForegroundColor Green
                }
            } else {
                Write-Host "Creating new Docker config..."
                $configDir = Split-Path $dockerConfig -Parent
                if (-not (Test-Path $configDir)) {
                    New-Item -ItemType Directory -Path $configDir | Out-Null
                }
                '{}' | Set-Content $dockerConfig
                Write-Host "✓ Created Docker config" -ForegroundColor Green
            }
            
            Write-Host ""
            Write-Host "Testing Docker access..."
            docker pull hello-world:latest 2>&1 | Out-Null
            if ($LASTEXITCODE -eq 0) {
                docker rmi hello-world:latest 2>&1 | Out-Null
                Write-Host "✓ Docker is working correctly!" -ForegroundColor Green
            } else {
                Write-Host "⚠ Docker test failed. Try restarting Docker Desktop." -ForegroundColor Yellow
            }
        }
        Write-Host ""
        Write-Host "You can now run: .\Makefile.ps1 build" -ForegroundColor Cyan
    }
    default {
        Write-Host "Unknown target: $Target"
        Write-Host "Available targets: up, down, build, test, lint, format, clean, ingest, demo, init-db, migrate, fix-docker-creds"
        exit 1
    }
}

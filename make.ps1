# PowerShell wrapper for Makefile commands
# Usage: .\make.ps1 <target>

param(
    [Parameter(Mandatory=$true)]
    [string]$Target
)

$ErrorActionPreference = "Stop"

function Invoke-MakeTarget {
    param([string]$Target)
    
    switch ($Target) {
        "up" {
            docker-compose up -d
        }
        "down" {
            docker-compose down
        }
        "build" {
            docker-compose build
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
            Write-Host "Ingesting RSS feed..." -ForegroundColor Cyan
            $body = @{
                feed_url = "https://feeds.yle.fi/uutiset/v1/recent.rss?publisherIds=YLE_UUTISET"
                publisher = "Yle"
                limit = 10
            } | ConvertTo-Json
            try {
                $response = Invoke-RestMethod -Uri "http://localhost:8000/ingest/rss" -Method Post -Body $body -ContentType "application/json"
                Write-Host "Success! Indexed $($response.indexed_chunks) chunks" -ForegroundColor Green
                return $response
            } catch {
                Write-Host "Error: $_" -ForegroundColor Red
                throw
            }
        }
        "demo" {
            Write-Host "Demo: Asking about recent news" -ForegroundColor Cyan
            $body = @{
                question = "Mitä uutisia on tänään?"
            } | ConvertTo-Json
            try {
                $response = Invoke-RestMethod -Uri "http://localhost:8000/chat" -Method Post -Body $body -ContentType "application/json"
                Write-Host "`nAnswer:" -ForegroundColor Yellow
                Write-Host $response.answer
                Write-Host "`nSources:" -ForegroundColor Yellow
                $response.sources | ForEach-Object { Write-Host "  $($_.label): $($_.title)" }
                return $response
            } catch {
                Write-Host "Error: $_" -ForegroundColor Red
                throw
            }
        }
        "init-db" {
            Write-Host "Initializing database..." -ForegroundColor Cyan
            docker-compose exec api python -c "from news_assistant.audit_db import get_engine, init_db; from news_assistant.settings import settings; engine = get_engine(settings.audit_db_url); init_db(engine)"
            Write-Host "Database initialized!" -ForegroundColor Green
        }
        "migrate" {
            docker-compose exec api alembic upgrade head
        }
        default {
            Write-Host "Unknown target: $Target" -ForegroundColor Red
            Write-Host "Available targets: up, down, build, test, lint, format, clean, ingest, demo, init-db, migrate" -ForegroundColor Yellow
            exit 1
        }
    }
}

Invoke-MakeTarget -Target $Target

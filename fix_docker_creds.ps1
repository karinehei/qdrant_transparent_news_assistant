# Fix Docker credential helper issues on Windows/PowerShell

Write-Host "Fixing Docker credential helper issues..." -ForegroundColor Cyan

$dockerConfig = if ($env:DOCKER_CONFIG) { $env:DOCKER_CONFIG } else { "$env:USERPROFILE\.docker\config.json" }
$backupFile = "${dockerConfig}.backup.$(Get-Date -Format 'yyyyMMdd_HHmmss')"

# Check if config exists
if (Test-Path $dockerConfig) {
    Write-Host "Backing up Docker config to: $backupFile"
    Copy-Item $dockerConfig $backupFile
    
    # Read and modify config
    try {
        $config = Get-Content $dockerConfig -Raw | ConvertFrom-Json
        
        # Remove credential helper properties
        if ($config.PSObject.Properties.Name -contains 'credsStore') {
            $config.PSObject.Properties.Remove('credsStore')
            Write-Host "Removed credsStore" -ForegroundColor Yellow
        }
        if ($config.PSObject.Properties.Name -contains 'credHelpers') {
            $config.PSObject.Properties.Remove('credHelpers')
            Write-Host "Removed credHelpers" -ForegroundColor Yellow
        }
        
        # Save updated config
        $config | ConvertTo-Json -Depth 10 | Set-Content $dockerConfig
        Write-Host "✓ Docker config updated" -ForegroundColor Green
    } catch {
        Write-Host "Error modifying config: $_" -ForegroundColor Red
        Write-Host "Trying alternative method..." -ForegroundColor Yellow
        # Fallback: remove lines manually
        $content = Get-Content $dockerConfig
        $content | Where-Object { $_ -notmatch '"credsStore"' -and $_ -notmatch '"credHelpers"' } | Set-Content "${dockerConfig}.tmp"
        Move-Item -Force "${dockerConfig}.tmp" $dockerConfig
        Write-Host "✓ Docker config updated (fallback method)" -ForegroundColor Green
    }
} else {
    Write-Host "Creating new Docker config without credential helper..."
    $configDir = Split-Path $dockerConfig -Parent
    if (-not (Test-Path $configDir)) {
        New-Item -ItemType Directory -Path $configDir | Out-Null
    }
    '{}' | Set-Content $dockerConfig
    Write-Host "✓ Created Docker config" -ForegroundColor Green
}

# Test Docker access
Write-Host ""
Write-Host "Testing Docker access..."
docker pull hello-world:latest 2>&1 | Out-Null
if ($LASTEXITCODE -eq 0) {
    docker rmi hello-world:latest 2>&1 | Out-Null
    Write-Host "✓ Docker is working correctly!" -ForegroundColor Green
    Write-Host ""
    Write-Host "You can now run: .\Makefile.ps1 build" -ForegroundColor Cyan
} else {
    Write-Host "⚠ Docker pull still has issues. Try:" -ForegroundColor Yellow
    Write-Host "  1. Restart Docker Desktop" -ForegroundColor Yellow
    Write-Host "  2. Check if Docker is running: docker info" -ForegroundColor Yellow
}

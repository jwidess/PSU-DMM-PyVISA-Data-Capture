# launch.ps1

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

# Virtual environment path
$VenvPath = Join-Path $ScriptDir ".venv"

# Create .venv if it doesn't exist
if (-not (Test-Path $VenvPath)) {
    Write-Host "Creating virtual environment in .venv..." -ForegroundColor Cyan
    python -m venv .venv
    
    # Activate and install requirements
    Write-Host "Installing dependencies..." -ForegroundColor Cyan
    . "$VenvPath\Scripts\Activate.ps1"
    pip install -r requirements.txt
} else {
    # Activate existing environment
    Write-Host "Activating virtual environment..." -ForegroundColor Green
    . "$VenvPath\Scripts\Activate.ps1"
}

Write-Host "Starting VISA Logger..." -ForegroundColor Cyan
python visa_logger.py

Start-Sleep -Seconds 5
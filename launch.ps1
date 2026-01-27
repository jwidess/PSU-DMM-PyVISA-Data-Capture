# launch.ps1

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

# Virtual environment path
$VenvName = "visa_logger_venv"
$VenvPath = Join-Path $env:USERPROFILE ".virtualenvs\$VenvName"

# Create .venv if it doesn't exist
if (-not (Test-Path $VenvPath)) {
    Write-Host "Creating virtual environment at $VenvPath..." -ForegroundColor Cyan
    python -m venv $VenvPath
    
    # Activate and install requirements
    Write-Host "Installing dependencies..." -ForegroundColor Cyan
    . "$VenvPath\Scripts\Activate.ps1"
    pip install -r requirements.txt
} else {
    # Activate existing environment
    Write-Host "Activating virtual environment at $VenvPath..." -ForegroundColor Green
    . "$VenvPath\Scripts\Activate.ps1"
}

Write-Host "Starting VISA Logger..." -ForegroundColor Cyan
python visa_logger.py

Start-Sleep -Seconds 5
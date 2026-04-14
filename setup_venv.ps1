# PowerShell script to set up the virtual environment for Sabeel Homeo Clinic AI Chatbot

$OutputEncoding = [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()

Write-Host "Setting up the virtual environment for Sabeel Homeo Clinic AI Chatbot..." -ForegroundColor Cyan

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "Python is not installed or not in PATH. Please install Python first." -ForegroundColor Red
    exit 1
}

Write-Host "Creating virtual environment..." -ForegroundColor Yellow
python -m venv venv

Write-Host "Activating virtual environment..." -ForegroundColor Yellow
& ".\venv\Scripts\Activate.ps1"

Write-Host "Upgrading pip..." -ForegroundColor Yellow
python -m pip install --upgrade pip

Write-Host "Installing dependencies from requirements.txt..." -ForegroundColor Yellow
pip install -r requirements.txt

Write-Host ""
Write-Host "Setup complete." -ForegroundColor Green
Write-Host ""
Write-Host "To activate the virtual environment later, run:" -ForegroundColor Cyan
Write-Host "    .\venv\Scripts\Activate.ps1" -ForegroundColor White
Write-Host ""
Write-Host "To start the server, run:" -ForegroundColor Cyan
Write-Host "    uvicorn main:app --reload" -ForegroundColor White
Write-Host ""
Write-Host "To run the test suite, run:" -ForegroundColor Cyan
Write-Host "    venv\Scripts\python.exe -m unittest discover -s tests -v" -ForegroundColor White

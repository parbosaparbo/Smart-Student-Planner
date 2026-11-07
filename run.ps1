# StudyMind AI Launcher
Set-Location -Path $PSScriptRoot
Write-Host "Starting StudyMind AI..." -ForegroundColor Cyan

$streamlit = Join-Path $PSScriptRoot ".venv\Scripts\streamlit.exe"
if (-not (Test-Path $streamlit)) {
    Write-Host "Virtualenv not found. Initializing..." -ForegroundColor Yellow
    uv venv --python 3.12
    uv pip install -r requirements.txt
}

Start-Process "http://localhost:8501"
& $streamlit run app.py


@echo off
title StudyMind AI
cd /d "%~dp0"

echo ========================================================
echo         StudyMind AI -- Native Desktop App
echo ========================================================
echo.

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found. Please wait...
    pause
    exit /b 1
)

echo Launching StudyMind AI Native Desktop Window...
".venv\Scripts\python.exe" desktop.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Fallback: starting in standard browser mode...
    start http://localhost:8501
    ".venv\Scripts\streamlit.exe" run app.py
)

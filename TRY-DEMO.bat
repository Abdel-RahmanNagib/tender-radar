@echo off
REM Try the app with sample (fictional) data - no internet needed.
cd /d "%~dp0"
where python >nul 2>nul || (echo Python is not installed. Download it from https://www.python.org/downloads/ and tick "Add Python to PATH". & pause & exit /b)
python scanner\run.py --demo
echo Opening the demo app at http://localhost:8765 - close this window to stop.
python scanner\run.py --serve-only

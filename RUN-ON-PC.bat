@echo off
REM Tender Radar - run on this PC: opens the app and checks every hour while this window is open.
cd /d "%~dp0"
where python >nul 2>nul || (echo Python is not installed. Download it from https://www.python.org/downloads/ and tick "Add Python to PATH". & pause & exit /b)
echo Tender Radar is running. The app opens at http://localhost:8765 - keep this window open.
python scanner\run.py --app --loop
pause

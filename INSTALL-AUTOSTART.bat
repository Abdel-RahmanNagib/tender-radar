@echo off
REM Start Tender Radar automatically (hidden) every time you sign in to Windows.
cd /d "%~dp0"
for /f "delims=" %%p in ('where pythonw') do (set "PYW=%%p" & goto found)
echo pythonw was not found. Install Python from https://www.python.org/downloads/ first. & pause & exit /b
:found
schtasks /Create /F /SC ONLOGON /TN "TenderRadar" /TR "\"%PYW%\" \"%~dp0scanner\run.py\" --app --loop --no-browser" /RL LIMITED
schtasks /Run /TN "TenderRadar"
echo.
echo Done. Tender Radar now starts when you sign in. Open http://localhost:8765 to use the app.
echo To remove it later run:  schtasks /Delete /TN TenderRadar /F
pause

@echo off
chcp 65001 >nul
setlocal EnableExtensions
title Tender Radar - office PC helper
set "HOME_DIR=%~dp0"
if "%HOME_DIR:~-1%"=="\" set "HOME_DIR=%HOME_DIR:~0,-1%"
cd /d "%HOME_DIR%"
if not exist "%HOME_DIR%\data" mkdir "%HOME_DIR%\data"
echo.
echo  Tender Radar - installing the office PC helper
echo  رادار المناقصات - تثبيت مساعد كمبيوتر المكتب
echo.

rem --- Python: the copy that comes with QGIS, else ArcGIS Pro, else an installed Python
set "PY="
set "PYDIR="
set "QGISDIR="
for /d %%Q in ("%ProgramFiles%\QGIS*") do for /d %%P in ("%%~Q\apps\Python3*") do if exist "%%~P\python.exe" set "PY=%%~P\python.exe" & set "PYDIR=%%~P" & set "QGISDIR=%%~Q"
if not defined PY if exist "%ProgramFiles%\ArcGIS\Pro\bin\Python\envs\arcgispro-py3\python.exe" set "PYDIR=%ProgramFiles%\ArcGIS\Pro\bin\Python\envs\arcgispro-py3"
if not defined PY if defined PYDIR set "PY=%PYDIR%\python.exe"
if not defined PY for /f "delims=" %%p in ('where python 2^>nul ^| findstr /v /i "WindowsApps"') do if not defined PY set "PY=%%p"
if not defined PY (
  echo  Python not found. Install Python 3 from python.org, then run this file again.
  echo  لم يتم العثور على Python. ثبّت Python 3 من python.org ثم شغّل هذا الملف مرة أخرى.
  pause
  exit /b 1
)
echo  Python: %PY%

rem --- the hourly job: run-scan.bat (environment for the bundled Python) started hidden by run-hidden.vbs
set "RUN=%HOME_DIR%\run-scan.bat"
> "%RUN%" echo @echo off
>> "%RUN%" echo chcp 65001 ^>nul
if defined QGISDIR >> "%RUN%" echo set "PATH=%QGISDIR%\bin;%PYDIR%;%%PATH%%"
>> "%RUN%" echo set "TR_DLL_DIRS=%QGISDIR%\bin;%PYDIR%;%PYDIR%\DLLs;%PYDIR%\Library\bin"
>> "%RUN%" echo set "PYTHONUTF8=1"
>> "%RUN%" echo set "PYTHONIOENCODING=utf-8"
>> "%RUN%" echo cd /d "%HOME_DIR%"
>> "%RUN%" echo "%PY%" "%HOME_DIR%\pc_launcher.py"
set "VBS=%HOME_DIR%\run-hidden.vbs"
> "%VBS%" echo CreateObject("WScript.Shell").Run """%RUN%""", 0, False

schtasks /Create /F /SC HOURLY /MO 1 /TN "TenderRadar PC Helper" /TR "wscript.exe \"%VBS%\"" >nul 2>&1
if errorlevel 1 (
  echo  Could not create the hourly task. Right-click this file and choose "Run as administrator".
  echo  تعذر إنشاء المهمة كل ساعة. اضغط على الملف بالزر الأيمن واختر Run as administrator.
  pause
  exit /b 1
)
echo  Hourly task created: TenderRadar PC Helper
echo.
echo  First scan now (about 1-2 minutes)...
echo  أول فحص الآن (دقيقة أو اثنتين)...
echo.
call "%RUN%"
echo.
echo  This PC's public key (not secret):
type "%HOME_DIR%\PUBLIC-KEY.txt"
echo.
echo  Done. The helper now runs every hour while this PC is on.
echo  تم. المساعد سيعمل تلقائياً كل ساعة طالما الكمبيوتر شغال.
echo.
pause

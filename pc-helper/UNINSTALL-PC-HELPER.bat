@echo off
chcp 65001 >nul
schtasks /Delete /F /TN "TenderRadar PC Helper"
echo.
echo  The hourly task was removed. You can now delete this folder.
echo  تم إيقاف المساعد. يمكنك الآن حذف هذا المجلد.
pause

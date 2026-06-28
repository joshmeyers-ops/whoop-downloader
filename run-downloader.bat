@echo off
REM Double-click launcher for the WHOOP + Wyze downloader.
cd /d "%~dp0"
echo Pulling your WHOOP and Wyze data...
echo.
".venv\Scripts\python.exe" -m downloader
echo.
echo ============================================================
echo  Done. Your CSV files are in the "out" folder:
echo    %~dp0out
echo ============================================================
echo.
pause

@echo off
REM Double-click launcher: WHOOP data only.
cd /d "%~dp0"
echo Pulling your WHOOP data only...
echo.
".venv\Scripts\python.exe" -m downloader --skip-wyze
echo.
echo ============================================================
echo  Done. WHOOP CSV files are in the "out" folder:
echo    %~dp0out
echo ============================================================
echo.
pause

@echo off
REM Double-click launcher: Wyze Scale data only.
cd /d "%~dp0"
echo Pulling your Wyze Scale data only...
echo.
".venv\Scripts\python.exe" -m downloader --skip-whoop
echo.
echo ============================================================
echo  Done. body_composition.csv is in the "out" folder:
echo    %~dp0out
echo ============================================================
echo.
pause

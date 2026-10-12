@echo off
title DepEd Project S.M.I.L.E. - Standalone Desktop Application
color 0B
cls
echo ======================================================================
echo    DEPARTMENT OF EDUCATION - PROJECT S.M.I.L.E. DESKTOP CLIENT
echo ======================================================================
echo  Starting Standalone Desktop Application...
echo  Both Desktop App and Web App share the exact same Realtime Database!
echo ======================================================================
echo.

cd /d "%~dp0"
python smile_desktop_app.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [!] An unexpected error occurred. Press any key to exit.
    pause >nul
)

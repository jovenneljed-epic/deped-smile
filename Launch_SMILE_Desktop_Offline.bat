@echo off
title DepEd Project S.M.I.L.E. - Standalone Desktop (Local Offline Mode)
color 0E
cls
echo ======================================================================
echo    DEPED S.M.I.L.E. - LOCAL OFFLINE / LAN SERVER MODE
echo ======================================================================
echo  Starting Desktop App with embedded local offline server...
echo ======================================================================
echo.

cd /d "%~dp0"
python smile_desktop_app.py --local

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [!] An unexpected error occurred. Press any key to exit.
    pause >nul
)

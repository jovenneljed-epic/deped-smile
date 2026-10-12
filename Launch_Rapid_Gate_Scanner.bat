@echo off
title DepEd Project S.M.I.L.E. - Rapid Gate Terminal
color 0A
cls
echo ======================================================================
echo    DEPED S.M.I.L.E. - ULTRA-FAST NATIVE RAPID GATE TERMINAL
echo ======================================================================
echo  Launching Native Desktop Gate Scanner...
echo  Connected to Live Real-Time Database!
echo ======================================================================
echo.

cd /d "%~dp0"
python smile_rapid_gate_app.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [!] An unexpected error occurred. Press any key to exit.
    pause >nul
)

@echo off
title DepEd Project S.M.I.L.E. - Live Internet Deployment
color 0B

echo =======================================================================
echo          PROJECT S.M.I.L.E. - PUBLIC INTERNET DEPLOYMENT
echo   School: Don Montano Central Integrated School
echo =======================================================================
echo.
echo [*] Checking local production web server on port 5000...
powershell -Command "(Invoke-WebRequest -Uri 'http://127.0.0.1:5000/login' -TimeoutSec 3 -ErrorAction SilentlyContinue).StatusCode" >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [*] Starting local Production Server in background...
    start /B python run_production.py
    timeout /t 3 >nul
) else (
    echo [+] Local server is already running on port 5000!
)

echo.
echo [*] Launching Cloudflare Global HTTPS Tunnel...
echo [*] A public HTTPS URL will be displayed below. Share this URL with parents and staff!
echo =======================================================================
echo.

cloudflared tunnel --url http://127.0.0.1:5000

pause

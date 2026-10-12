@echo off
title DepEd Project S.M.I.L.E. - Web Server for LAN / Wi-Fi
color 0E
cls
echo ======================================================================
echo    DEPED PROJECT S.M.I.L.E. - LOCAL NETWORK HOST SERVER
echo ======================================================================
echo  This host server allows other laptops, mobile phones, and tablets
echo  on the same school Wi-Fi or Local Network to access the Web App!
echo.
echo  Standalone Desktop apps and Web users will share the EXACT SAME
echo  REAL-TIME DATABASE with immediate synchronization!
echo ======================================================================
echo.

cd /d "%~dp0"
python -c "import socket; s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.connect(('8.8.8.8', 80)); ip = s.getsockname()[0]; s.close(); print(' >>> Your Local Network (Wi-Fi) Web App URL: http://' + ip + ':5000 <<<')" 2>nul
echo.
echo Starting server on 0.0.0.0:5000...
echo.

python -c "import app; app.app.run(host='0.0.0.0', port=5000, threaded=True)"

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [!] Server stopped.
    pause >nul
)

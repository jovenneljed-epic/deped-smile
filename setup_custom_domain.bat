@echo off
title DepEd Project S.M.I.L.E. - Custom Domain Setup
color 0B
cls

echo ======================================================================
echo           DEPED PROJECT S.M.I.L.E. - CUSTOM DOMAIN CONFIGURATOR
echo ======================================================================
echo  This tool helps you bind your own custom school domain (e.g.:
echo  smile.donmontanocis.edu.ph or deped-smile.ph) to this local server.
echo.
echo  REQUIREMENT: A free Cloudflare account (https://dash.cloudflare.com)
echo               with your school domain added to Cloudflare DNS.
echo ======================================================================
echo.
echo  [1] Step 1: Login to Cloudflare (Opens web browser to authorize)
echo  [2] Step 2: Create Named Tunnel (deped-smile)
echo  [3] Step 3: Route DNS (Bind your custom domain or subdomain)
echo  [4] Step 4: Run Named Tunnel (Start serving traffic)
echo  [5] Step 5: Install Tunnel as Windows Background Service (Auto-Start)
echo  [6] Launch Quick Temporary Tunnel (Random trycloudflare.com URL)
echo  [7] Exit
echo.
set /p choice="Enter choice [1-7]: "

if "%choice%"=="1" goto LOGIN
if "%choice%"=="2" goto CREATE_TUNNEL
if "%choice%"=="3" goto ROUTE_DNS
if "%choice%"=="4" goto RUN_TUNNEL
if "%choice%"=="5" goto INSTALL_SERVICE
if "%choice%"=="6" goto QUICK_TUNNEL
if "%choice%"=="7" goto END
goto END

:LOGIN
echo.
echo Authorizing Cloudflare... A browser window will open.
"C:\Program Files (x86)\cloudflared\cloudflared.exe" tunnel login
echo.
pause
goto END

:CREATE_TUNNEL
echo.
set /p tname="Enter tunnel name (Default: deped-smile): "
if "%tname%"=="" set tname=deped-smile
"C:\Program Files (x86)\cloudflared\cloudflared.exe" tunnel create %tname%
echo.
echo Tunnel '%tname%' created! Note the Tunnel ID shown above.
pause
goto END

:ROUTE_DNS
echo.
set /p tname="Enter tunnel name (Default: deped-smile): "
if "%tname%"=="" set tname=deped-smile
set /p cdomain="Enter your full domain (e.g. smile.mydomain.com): "
if "%cdomain%"=="" (
    echo [ERROR] Domain cannot be blank.
    pause
    goto END
)
"C:\Program Files (x86)\cloudflared\cloudflared.exe" tunnel route dns %tname% %cdomain%
echo.
echo Domain %cdomain% is now routed to tunnel %tname%!
pause
goto END

:RUN_TUNNEL
echo.
set /p tname="Enter tunnel name (Default: deped-smile): "
if "%tname%"=="" set tname=deped-smile
echo Starting tunnel %tname% forwarding to http://127.0.0.1:5000...
"C:\Program Files (x86)\cloudflared\cloudflared.exe" tunnel run --url http://127.0.0.1:5000 %tname%
pause
goto END

:INSTALL_SERVICE
echo.
echo Installing cloudflared as an automatic Windows System Service...
"C:\Program Files (x86)\cloudflared\cloudflared.exe" service install
echo Service installed! It will start automatically when Windows boots.
pause
goto END

:QUICK_TUNNEL
echo.
echo Launching Quick Tunnel on trycloudflare.com...
"C:\Program Files (x86)\cloudflared\cloudflared.exe" tunnel --url http://127.0.0.1:5000
pause
goto END

:END
exit /b

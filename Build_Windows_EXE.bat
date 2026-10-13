@echo off
title DepEd Project S.M.I.L.E. - Windows Executable & Setup Builder
color 0B
cls
echo ======================================================================
echo    DEPARTMENT OF EDUCATION - PROJECT S.M.I.L.E. BUILD PIPELINE
echo ======================================================================
echo  1. Building Standalone Client: dist\DepEd_SMILE.exe
echo  2. Building Setup Installer:   dist\DepEd_SMILE_Setup.exe
echo ======================================================================
echo.

cd /d "%~dp0"

echo [*] Checking PyInstaller...
python -m PyInstaller --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [*] Installing PyInstaller...
    python -m pip install pyinstaller
)

echo.
echo [*] Step 1/2: Compiling Standalone Application (DepEd_SMILE.exe)...
python build_desktop_exe.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [!] Error compiling DepEd_SMILE.exe!
    pause
    exit /b %ERRORLEVEL%
)

echo.
echo [*] Step 2/2: Compiling Windows Setup Installer (DepEd_SMILE_Setup.exe)...
python build_installer.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [!] Error compiling DepEd_SMILE_Setup.exe!
    pause
    exit /b %ERRORLEVEL%
)

echo.
echo ======================================================================
echo  [ALL COMPLETE] Production Windows Executables Built Successfully!
echo ======================================================================
echo  Output Directory: %~dp0dist\
echo  Files Generated:
echo   - dist\DepEd_SMILE.exe        (Standalone Portable App)
echo   - dist\DepEd_SMILE_Setup.exe  (Windows Setup Wizard Installer)
echo ======================================================================
echo.
pause

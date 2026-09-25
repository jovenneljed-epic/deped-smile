@echo off
title DepEd Project S.M.I.L.E. - Push to GitHub & Vercel
color 0A
cls

echo ======================================================================
echo         DEPED PROJECT S.M.I.L.E. - GITHUB & VERCEL DEPLOYER
echo ======================================================================
echo  This script will commit your project and push it to your GitHub account.
echo  Once on GitHub, Vercel will automatically deploy it for FREE!
echo ======================================================================
echo.

:: Ensure git is in PATH
where git >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Git is not installed or not found in PATH.
    echo Please install Git from https://git-scm.com/
    pause
    exit /b 1
)

:: Initialize git repository if not already done
if not exist ".git" (
    echo [*] Initializing local Git repository...
    git init
    git branch -M main
)

:: Stage all files
echo [*] Staging all files...
git add .

:: Commit
set /p commit_msg="Enter commit message (Press Enter for default): "
if "%commit_msg%"=="" set commit_msg="DepEd Project S.M.I.L.E. - Ready for GitHub & Vercel deployment"
git commit -m "%commit_msg%"

echo.
echo ======================================================================
echo                     ENTER YOUR GITHUB REPOSITORY URL
echo ======================================================================
echo  1. Create a NEW empty repository on https://github.com/new
echo     (Name it: project-smile or deped-smile)
echo     (DO NOT check "Add README" or .gitignore)
echo  2. Copy the repository URL (e.g. https://github.com/YOUR_USER/project-smile.git)
echo ======================================================================
echo.
set /p repo_url="Paste your GitHub Repository URL here: "

if "%repo_url%"=="" (
    echo [!] No URL entered. Changes committed locally.
    pause
    exit /b 0
)

:: Check if remote origin exists
git remote get-url origin >nul 2>nul
if %errorlevel% equ 0 (
    git remote set-url origin %repo_url%
) else (
    git remote add origin %repo_url%
)

echo.
echo [*] Pushing code to GitHub (main branch)...
git push -u origin main

if %errorlevel% equ 0 (
    echo.
    echo ======================================================================
    echo           SUCCESSFULLY PUSHED TO GITHUB!
    echo ======================================================================
    echo  Next steps to deploy on Vercel:
    echo  1. Go to: https://vercel.com/new
    echo  2. Click "Import" next to your GitHub repository.
    echo  3. Framework Preset: Leave as "Other" (Vercel reads vercel.json).
    echo  4. Click "Deploy".
    echo.
    echo  Your DepEd Project S.M.I.L.E. will be live with a free .vercel.app domain!
    echo ======================================================================
) else (
    echo.
    echo [!] Push failed. Please verify your GitHub credentials or Personal Access Token.
)

pause

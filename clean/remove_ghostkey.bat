@echo off
title GhostKey - Cleanup Tool
cd /d "%~dp0"

echo ====================================
echo    GhostKey - Complete Removal
echo ====================================
echo.

:: Step 1: Kill all Python processes running the keylogger
echo [1/5] Killing keylogger process...
taskkill /f /im python.exe >nul 2>&1
echo   Done.

:: Step 2: Remove startup shortcut
echo [2/5] Removing startup entry...
del /f /q "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\WindowsUpdateHelper.lnk" >nul 2>&1
echo   Done.

:: Step 3: Remove the keylogger file
echo [3/5] Deleting keylogger files...
del /f /q "%APPDATA%\Microsoft\Windows\WindowsUpdateHelper.py" >nul 2>&1
echo   Done.

:: Step 4: Also remove from registry (if any)
echo [4/5] Checking registry for persistence...
reg delete "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v "WindowsUpdateHelper" /f >nul 2>&1
reg delete "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v "GhostKey" /f >nul 2>&1
echo   Done.

:: Step 5: Clean any temp files
echo [5/5] Cleaning temporary files...
del /f /q "%TEMP%\gk.py" >nul 2>&1
echo   Done.

echo.
echo ====================================
echo     Removal Complete!
echo ====================================
echo.
echo The following has been removed:
echo   - Running keylogger process
echo   - Startup shortcut
echo   - Keylogger files from APPDATA
echo   - Registry entries (if any)
echo   - Temporary files
echo.
echo System is clean.
echo.
pause
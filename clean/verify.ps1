# Check if keylogger is still running
$process = Get-Process -Name "python" -ErrorAction SilentlyContinue
if ($process) {
    Write-Host "Python is still running. Check if it's the keylogger." -ForegroundColor Yellow
} else {
    Write-Host "No Python processes running. Clean." -ForegroundColor Green
}

# Check if files still exist
$test1 = Test-Path "$env:APPDATA\Microsoft\Windows\WindowsUpdateHelper.py"
$test2 = Test-Path "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup\WindowsUpdateHelper.lnk"

if (-not $test1 -and -not $test2) {
    Write-Host "No GhostKey files found on disk. Clean." -ForegroundColor Green
} else {
    Write-Host "Traces still found. Run removal again." -ForegroundColor Red
}

pause
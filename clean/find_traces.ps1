# Deep scan for any GhostKey traces
Write-Host "Scanning for GhostKey traces..." -ForegroundColor Yellow

# Check common locations
$locations = @(
    "$env:APPDATA\Microsoft\Windows\",
    "$env:TEMP\",
    "$env:LOCALAPPDATA\Temp\",
    "C:\Users\*\AppData\Roaming\Microsoft\Windows\",
    "C:\Users\*\Downloads\"
)

foreach ($loc in $locations) {
    $files = Get-ChildItem -Path $loc -Filter "*ghostkey*" -ErrorAction SilentlyContinue
    foreach ($file in $files) {
        Write-Host "  Found: $($file.FullName)" -ForegroundColor Red
        Remove-Item -Path $file.FullName -Force
        Write-Host "  Removed!" -ForegroundColor Green
    }
    
    $files2 = Get-ChildItem -Path $loc -Filter "*WindowsUpdateHelper*" -ErrorAction SilentlyContinue
    foreach ($file in $files2) {
        Write-Host "  Found: $($file.FullName)" -ForegroundColor Red
        Remove-Item -Path $file.FullName -Force
        Write-Host "  Removed!" -ForegroundColor Green
    }
}

# Check all startup locations
Write-Host "`nChecking startup locations..." -ForegroundColor Yellow
$startupFolders = @(
    "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup\",
    "$env:ProgramData\Microsoft\Windows\Start Menu\Programs\StartUp\"
)

foreach ($folder in $startupFolders) {
    $lnk = Get-ChildItem -Path $folder -Filter "*WindowsUpdateHelper*" -ErrorAction SilentlyContinue
    if ($lnk) {
        Remove-Item -Path $lnk.FullName -Force
        Write-Host "  Removed startup shortcut: $($lnk.Name)" -ForegroundColor Green
    }
}

Write-Host "`nScan complete!" -ForegroundColor Green

pause
@echo off
setlocal EnableExtensions EnableDelayedExpansion

REM ============================================================
REM  picotool_bootsel.bat
REM  - Downloads latest Windows x64 picotool from raspberrypi/pico-sdk-tools
REM  - Installs locally next to this .bat (no admin, no system PATH changes)
REM  - Runs: picotool reboot -f -u
REM ============================================================

set "BASEDIR=%~dp0"
set "TOOLS_DIR=%BASEDIR%picotool"
set "ZIP_PATH=%TOOLS_DIR%\picotool.zip"
set "EXE_PATH=%TOOLS_DIR%\picotool.exe"
set "STAMP_PATH=%TOOLS_DIR%\installed_version.txt"

REM --- Create tools dir ---
if not exist "%TOOLS_DIR%" mkdir "%TOOLS_DIR%" >nul 2>&1

REM --- If already installed, skip download ---
if exist "%EXE_PATH%" goto :run

echo Installing picotool (Windows x64) locally...
echo.

REM --- Use PowerShell to:
REM     1) Query GitHub latest release for raspberrypi/pico-sdk-tools
REM     2) Pick the x64 Windows picotool zip asset
REM     3) Download it
REM     4) Extract
REM     5) Copy picotool.exe to a flat path: %TOOLS_DIR%\picotool.exe
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ErrorActionPreference='Stop';" ^
  "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 -bor [Net.SecurityProtocolType]::Tls13;" ^
  "$repo='raspberrypi/pico-sdk-tools';" ^
  "$api='https://api.github.com/repos/' + $repo + '/releases/latest';" ^
  "$rel=Invoke-RestMethod -Uri $api -Headers @{ 'User-Agent'='picotool-bat' };" ^
  "$asset=$rel.assets | Where-Object { $_.name -match '^picotool-.*-x64-win\.zip$' } | Select-Object -First 1;" ^
  "if(-not $asset){ throw 'Could not find a picotool x64 Windows zip asset in the latest release.' }" ^
  "$zip='%ZIP_PATH%';" ^
  "$tools='%TOOLS_DIR%';" ^
  "Write-Host ('Downloading: ' + $asset.name);" ^
  "Invoke-WebRequest -Uri $asset.browser_download_url -OutFile $zip -UseBasicParsing;" ^
  "Write-Host 'Extracting...';" ^
  "Expand-Archive -Force -Path $zip -DestinationPath $tools;" ^
  "$exe = Get-ChildItem -Path $tools -Recurse -Filter picotool.exe | Select-Object -First 1;" ^
  "if(-not $exe){ throw 'picotool.exe not found after extraction (unexpected package layout).' }" ^
  "Copy-Item -Force -Path $exe.FullName -Destination ('%EXE_PATH%');" ^
  "Set-Content -Path '%STAMP_PATH%' -Value ($asset.name + ' | ' + $rel.tag_name);" ^
  "Remove-Item -Force $zip;" ^
  "Write-Host 'Installed to: %EXE_PATH%';"

if errorlevel 1 (
  echo.
  echo ERROR: picotool install failed.
  echo - Check internet access / proxy / GitHub availability.
  echo - If behind a corporate proxy, PowerShell may need proxy config.
  echo.
  pause
  exit /b 1
)

:run
echo.
echo Using: "%EXE_PATH%"
if not exist "%EXE_PATH%" (
  echo ERROR: picotool.exe missing at expected location.
  pause
  exit /b 1
)

echo Rebooting RP2040 into BOOTSEL mode...
"%EXE_PATH%" reboot -f -u
set "RC=%ERRORLEVEL%"

echo.
if not "%RC%"=="0" (
  echo picotool returned errorlevel %RC%.
  echo - Ensure the device is connected and accessible.
  echo - If it's already in BOOTSEL, picotool may not see it as a running device.
  echo - In some cases you need to remove the "RP2" or "Reset" USB devices in Windows Device Manager
) else (
  echo Done.
)

echo.
if exist "%STAMP_PATH%" (
  echo Installed version:
  type "%STAMP_PATH%"
)

pause
endlocal

@echo off
cd /d "%~dp0"
if not exist "App\FM_GPTPRO.exe" goto missing
if not exist "App\_internal\" goto missing
start "" "App\FM_GPTPRO.exe"
exit /b 0
:missing
echo Desktop package is missing or incomplete: App\FM_GPTPRO.exe and App\_internal are required.
echo Build from the delivery root: powershell -NoProfile -ExecutionPolicy Bypass -File tools\BuildDesktop.ps1
echo Or obtain the complete Windows release package. See README.md.
exit /b 1

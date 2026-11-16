@echo off
rem ASCII-only launcher: Chinese guidance lives in tools\StartupHelp.ps1 so that
rem cmd.exe never has to parse UTF-8 text with a non-UTF-8 code page.
cd /d "%~dp0"
if not exist "App\FM_GPTPRO.exe" goto missing
if not exist "App\_internal\" goto missing
start "" "App\FM_GPTPRO.exe"
exit /b 0
:missing
echo.
echo Desktop package missing: App\FM_GPTPRO.exe or App\_internal\ not found.
echo This GitHub repository stores sources only (.gitignore excludes App\).
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\StartupHelp.ps1"
pause
exit /b 1

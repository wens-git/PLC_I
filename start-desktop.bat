@echo off
cd /d "%~dp0"
python desktop_launcher.py
if errorlevel 1 pause

@echo off
REM Create desktop shortcut to AiChrome
cd /d "%~dp0"
powershell -ExecutionPolicy Bypass -File CreateDesktopShortcut.ps1

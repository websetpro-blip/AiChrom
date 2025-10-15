@echo off
echo Создание ярлыка AiChrome на рабочем столе...

powershell -ExecutionPolicy Bypass -File "%~dp0CreateDesktopShortcut.ps1"

echo.
echo Готово! Ярлык AiChrome создан на рабочем столе.
pause

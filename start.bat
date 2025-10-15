@echo off
title Multi-Browser Manager
echo ============================================
echo   🌐 Multi-Browser Manager v1.0
echo   Бесплатный аналог Dolphin Anty Browser
echo ============================================
echo.

REM Проверяем наличие Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ ОШИБКА: Python не найден!
    echo.
    echo Для работы приложения необходимо установить Python 3.7+
    echo Скачайте с https://python.org
    echo.
    pause
    exit /b 1
)

echo ✅ Python найден
echo 🚀 Запуск Multi-Browser Manager...
echo.

REM Запускаем приложение
python multi_browser_manager.py

if errorlevel 1 (
    echo.
    echo ❌ Ошибка при запуске приложения
    echo Проверьте что файл multi_browser_manager.py находится в той же папке
    echo.
    pause
)

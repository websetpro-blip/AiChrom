#!/bin/bash

# Multi-Browser Manager Launcher Script
# Совместимость: Linux, macOS

echo "============================================"
echo "  🌐 Multi-Browser Manager v1.0"
echo "  Бесплатный аналог Dolphin Anty Browser"
echo "============================================"
echo ""

# Проверяем наличие Python
if ! command -v python3 &> /dev/null; then
    if ! command -v python &> /dev/null; then
        echo "❌ ОШИБКА: Python не найден!"
        echo ""
        echo "Для работы приложения необходимо установить Python 3.7+"
        echo ""
        echo "Ubuntu/Debian: sudo apt install python3 python3-tk"
        echo "macOS: brew install python-tk"
        echo "или скачайте с https://python.org"
        echo ""
        read -p "Нажмите Enter для выхода..."
        exit 1
    else
        PYTHON_CMD="python"
    fi
else
    PYTHON_CMD="python3"
fi

echo "✅ Python найден"

# Проверяем наличие tkinter
$PYTHON_CMD -c "import tkinter" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "❌ ОШИБКА: tkinter не найден!"
    echo ""
    echo "Установите tkinter:"
    echo "Ubuntu/Debian: sudo apt install python3-tk"
    echo "macOS: обычно включен в Python"
    echo ""
    read -p "Нажмите Enter для выхода..."
    exit 1
fi

echo "✅ tkinter найден"
echo "🚀 Запуск Multi-Browser Manager..."
echo ""

# Проверяем наличие главного файла
if [ ! -f "multi_browser_manager.py" ]; then
    echo "❌ ОШИБКА: Файл multi_browser_manager.py не найден!"
    echo "Убедитесь что файл находится в той же папке что и этот скрипт"
    echo ""
    read -p "Нажмите Enter для выхода..."
    exit 1
fi

# Запускаем приложение
$PYTHON_CMD multi_browser_manager.py

# Проверяем код выхода
if [ $? -ne 0 ]; then
    echo ""
    echo "❌ Ошибка при запуске приложения"
    echo "Проверьте логи выше для подробностей"
    echo ""
    read -p "Нажмите Enter для выхода..."
fi

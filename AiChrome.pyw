"""
AiChrome Browser Manager - GUI launcher без консоли
Запускает multi_browser_manager.py без отображения командной строки
"""
import sys
from pathlib import Path

# Добавляем директорию проекта в путь
sys.path.insert(0, str(Path(__file__).parent))

# Импортируем и запускаем главное приложение
from multi_browser_manager import main

if __name__ == "__main__":
    main()

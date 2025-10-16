# AiChrome
Lightweight Chromium-based browser manager with automation utilities.

Quickstart
1. Install Python 3.10+
2. Create virtualenv: `python -m venv .venv`
3. Activate and install: `pip install -r requirements.txt`
4. Run: `python AiChrome.pyw` or use provided `start.bat` on Windows.

Notes
- This repository contains build artifacts in `dist/` and `build/` which are ignored by `.gitignore`.
- If you plan to add large model or binary files, consider using Git LFS.

Contact
Open issues and PRs on GitHub.

# AiChrome
Менеджер браузерных профилей с лёгким антидетектом и встроенным Proxy Lab. Приложение запускает отдельный Chrome для каждого профиля, фиксирует запуски через lock-файлы и хранит настройки в `browser_profiles.json`.

## Возможности
- Отдельные профили Chrome с каталогами в `profiles/<id>` и защитой от повторного запуска через `.aichrome.lock`.
- Автоматический выбор портативного Chrome из `tools/chrome` или fallback на системный браузер.
- Proxy Lab: парсинг свободного формата прокси, многопоточная проверка через `ipify` + `ip-api`, добавление в `proxies.csv`.
- Sticky-привязка прокси на 10 минут и автоподбор живого прокси по стране/типу (`http`, `socks4`, `socks5`).
- Self-Test и запуск профиля с учётом User-Agent, языка и часового пояса.
- Лёгкая сборка EXE через PyInstaller.

## Быстрый старт
1. `pip install -r requirements.txt`
2. Запусти UI: `python multi_browser_manager.py`
3. В Proxy Lab вставь список прокси (форматы: scheme://user:pass@ip:port | ip:port:user:pass | ip:port).
4. Нажми **Парсить → Валидировать → Добавить в пул**.
5. Создай профиль, выбери страну/тип, нажми **Автопрокси** → **Self-Test** → **Запустить**.

## Сборка EXE
`build_executable.bat`

Логи: `logs/launcher.log`. Пул: `proxies.csv`. Sticky и кэш: `cache/*.json`.

## Структура проекта
- `multi_browser_manager.py` — основное приложение Tk/ttk (fallback на ttkbootstrap).
- `proxy/` — модели прокси, парсер, валидация и пул с sticky-кэшем.
- `tools/` — логирование, выбор Chrome, менеджер lock-файлов.
- `ui/proxy_lab.py` — Proxy Lab-frame для вставки в окна настроек.
- `worker_chrome.py` — запуск Chrome с MV3-расширением для авторизации прокси.

## Примечания
- Настройки и профили сохраняются автоматически в `browser_profiles.json` и `profiles/`.
- Для проверки Self-Test используется `requests` и требуется рабочее интернет-соединение.
- Портативный Chrome можно положить в `tools/chrome/`; иначе будет использован системный.

## Per-profile proxy & MV3 extension
AiChrome поддерживает пер-профильные прокси с автоматической аутентификацией.
- Каждому профилю соответствует свой `--user-data-dir`, поэтому куки и хранилище изолированы.

---

## Architecture Overview / Обзор архитектуры

### Core Components / Основные компоненты

#### 1. MultiBrowserManager (`multi_browser_manager.py`)
The main orchestrator that manages multiple browser instances and coordinates worker operations.

**Key responsibilities:**
- Profile management and storage
- Worker lifecycle management
- Proxy assignment and rotation
- UI event handling
- Configuration persistence

**Main classes:**
- `MultiBrowserManager`: Central controller for all browser operations
- Integrates with Proxy Lab for proxy management
- Handles profile creation, editing, and deletion

#### 2. WorkerChrome (`worker_chrome.py`)
Individual browser worker that controls a single Chrome instance.

**Key responsibilities:**
- Chrome process lifecycle (launch, monitor, terminate)
- Lock file management to prevent duplicate launches
- MV3 extension injection for proxy authentication
- Profile-specific configuration
- User-Agent and timezone spoofing

**Features:**
- Isolated `--user-data-dir` per profile
- Automatic Chrome binary detection (portable vs system)
- Extension-based proxy authentication (no command-line proxy)
- Lock file protection against concurrent launches

#### 3. Proxy Management (`proxy/`)

**`proxy_manager.py`**: Main proxy pool management
- Load/save proxy pool from `proxies.csv`
- Sticky assignment (10-minute timeout)
- Country and protocol filtering
- Auto-selection based on criteria

**`proxy_validator.py`**: Multi-threaded proxy validation
- Validates via `ipify` (IP check) and `ip-api` (geolocation)
- Concurrent validation with configurable threads
- Timeout handling and error recovery

**`proxy_parser.py`**: Flexible proxy format parser
- Supports multiple formats:
  - `scheme://user:pass@ip:port`
  - `ip:port:user:pass`
  - `ip:port`
- Auto-detection of proxy type

#### 4. UI Components (`ui/`)

**`proxy_lab.py`**: Proxy management interface
- Proxy parsing and validation UI
- Pool management controls
- Integration with main window

### Data Flow / Поток данных

```
User Input → MultiBrowserManager → WorkerChrome → Chrome Process
                ↓                      ↓
            ProxyManager          Lock File Manager
                ↓                      ↓
            proxies.csv          .aichrome.lock
```

### File Structure / Структура файлов

```
AiChrom/
├── multi_browser_manager.py    # Main application entry
├── worker_chrome.py             # Individual browser worker
├── browser_profiles.json        # Profile configurations
├── proxies.csv                  # Proxy pool
├── proxy/                       # Proxy management modules
│   ├── proxy_manager.py
│   ├── proxy_validator.py
│   ├── proxy_parser.py
│   └── models.py
├── ui/                          # User interface components
│   └── proxy_lab.py
├── tools/                       # Utility modules
│   ├── logger.py
│   ├── chrome_finder.py
│   └── lock_manager.py
├── profiles/                    # Chrome user data directories
│   └── <profile_id>/
├── cache/                       # Temporary cache files
├── logs/                        # Application logs
└── tests/                       # Test suite
```

### Extension Points / Точки расширения

1. **Custom Proxy Validators**: Add new validation endpoints in `proxy_validator.py`
2. **Additional Anti-detect Features**: Extend `WorkerChrome` with more fingerprint randomization
3. **Profile Templates**: Create preset configurations in `browser_profiles.json`
4. **UI Themes**: Customize ttkbootstrap themes in main application

---

## Usage Examples / Примеры использования

### Example 1: Creating and Launching a Profile

```python
from multi_browser_manager import MultiBrowserManager

# Initialize manager
manager = MultiBrowserManager()

# Create a new profile
profile = manager.create_profile(
    name="Test Profile",
    proxy_country="US",
    proxy_type="http"
)

# Auto-assign proxy
manager.auto_assign_proxy(profile)

# Launch browser
manager.launch_profile(profile.id)
```

### Example 2: Working with Proxy Pool

```python
from proxy.proxy_manager import ProxyManager
from proxy.proxy_validator import ProxyValidator

# Initialize proxy manager
proxy_mgr = ProxyManager("proxies.csv")

# Add proxies from text
proxies_text = """
http://user:pass@123.45.67.89:8080
98.76.54.32:3128
socks5://proxy.example.com:1080
"""

parsed = proxy_mgr.parse_proxies(proxies_text)

# Validate proxies
validator = ProxyValidator()
valid_proxies = validator.validate_batch(parsed, threads=10)

# Add to pool
proxy_mgr.add_to_pool(valid_proxies)
```

### Example 3: Programmatic Browser Control

```python
from worker_chrome import WorkerChrome
import asyncio

async def automated_task():
    # Create worker
    worker = WorkerChrome(
        profile_id="profile_001",
        user_data_dir="profiles/profile_001",
        proxy="http://user:pass@proxy.example.com:8080"
    )
    
    try:
        # Launch Chrome
        await worker.launch()
        
        # Wait for browser to be ready
        await asyncio.sleep(3)
        
        # Perform automation tasks here
        # (integrate with Selenium/Playwright if needed)
        
    finally:
        # Clean up
        await worker.close()

# Run the task
asyncio.run(automated_task())
```

### Example 4: Sticky Proxy Assignment

```python
from proxy.proxy_manager import ProxyManager

proxy_mgr = ProxyManager("proxies.csv")

# Get proxy for profile (sticky for 10 minutes)
proxy1 = proxy_mgr.get_sticky_proxy(
    profile_id="profile_001",
    country="US",
    proxy_type="http"
)

# Same proxy will be returned within 10 minutes
proxy2 = proxy_mgr.get_sticky_proxy(
    profile_id="profile_001",
    country="US",
    proxy_type="http"
)

assert proxy1 == proxy2  # True (within timeout)
```

---

## Running Tests / Запуск тестов

### Prerequisites

Make sure you have pytest installed:
```bash
pip install pytest pytest-asyncio
```

### Running All Tests

```bash
# Run all tests with verbose output
pytest -v

# Run with coverage
pytest --cov=. --cov-report=html

# Run specific test file
pytest test_example.py -v

# Run with print output (useful for debugging)
pytest -v -s
```

### Running Specific Test Classes

```bash
# Run only browser initialization tests
pytest test_example.py::TestBrowserInitialization -v

# Run only proxy-related tests
pytest tests/test_proxy_manager.py -v

# Run clipboard tests
pytest test_clipboard.py -v
```

### Test Structure

The test suite includes:

1. **test_example.py** - Comprehensive examples covering:
   - Browser initialization
   - Basic browser operations
   - Multi-worker management
   - Error handling

2. **test_clipboard.py** - Clipboard operations
3. **test_ctrl_cv.py** - Keyboard shortcuts and copy/paste
4. **test_launch_profile.py** - Profile launching and management

### Writing New Tests

Follow the pattern in `test_example.py`:

```python
import pytest

class TestYourFeature:
    """Test suite for your feature."""
    
    def test_something(self):
        """
        Test description.
        
        This test verifies:
        - Point 1
        - Point 2
        """
        # Your test code
        assert True
    
    @pytest.mark.asyncio
    async def test_async_operation(self):
        """Test async operations."""
        result = await some_async_function()
        assert result is not None
```

### Continuous Integration

Tests can be integrated into CI/CD pipelines:

```yaml
# Example GitHub Actions workflow
- name: Run tests
  run: |
    pip install -r requirements.txt
    pip install pytest pytest-asyncio
    pytest -v
```

---

## Contributing / Участие в разработке

See [Issue #1](https://github.com/websetpro-blip/AiChrom/issues/1) for the current improvement checklist.

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Make your changes with tests
4. Submit a pull request

---

## Performance and Load Testing

For load testing guidelines and performance optimization recommendations, see [PERFORMANCE.md](PERFORMANCE.md).

---

## License

See LICENSE file for details.

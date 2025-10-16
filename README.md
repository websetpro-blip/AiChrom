# AiChrome
Lightweight Chromium-based browser manager with automation utilities.
Quickstart
1. Install Python 3.10+
2. Create virtualenv: 
`python -m venv .venv`
3. Activate and install: 
`pip install -r requirements.txt`
4. Run: 
`python AiChrome.pyw`
 or use provided 
`start.bat`
 on Windows.
Notes
- This repository contains build artifacts in 
`dist/`
 and 
`build/`
 which are ignored by 
`.gitignore`
.
- If you plan to add large model or binary files, consider using Git LFS.
Contact
Open issues and PRs on GitHub.
# AiChrome
Менеджер браузерных профилей с лёгким антидетектом и встроенным Proxy Lab. Приложение запускает отдельный Chrome для каждого профиля, фиксирует запуски через lock-файлы и хранит настройки в 
`browser_profiles.json`
.
## Возможности
- Отдельные профили Chrome с каталогами в 
`profiles/<id>`
 и защитой от повторного запуска через 
`.aichrome.lock`
.
- Автоматический выбор портативного Chrome из 
`tools/chrome`
 или fallback на системный браузер.
- Proxy Lab: парсинг свободного формата прокси, многопоточная проверка через 
`ipify`
 + 
`ip-api`
, добавление в 
`proxies.csv`
.
- Sticky-привязка прокси на 10 минут и автоподбор живого прокси по стране/типу (
`http`
, 
`socks4`
, 
`socks5`
).
- Self-Test и запуск профиля с учётом User-Agent, языка и часового пояса.
- Лёгкая сборка EXE через PyInstaller.
## Быстрый старт
1. 
`pip install -r requirements.txt`
2. Запусти UI: 
`python multi_browser_manager.py`
3. В Proxy Lab вставь список прокси (форматы: scheme://user:pass@ip:port | ip:port:user:pass | ip:port).
4. Нажми 
**Парсить → Валидировать → Добавить в пул**
.
5. Создай профиль, выбери страну/тип, нажми 
**Автопрокси**
 → 
**Self-Test**
 → 
**Запустить**
.
## Сборка EXE
`build_executable.bat`
Логи: 
`logs/launcher.log`
. Пул: 
`proxies.csv`
. Sticky и кэш: 
`cache/*.json`
.

## План развития / Development Roadmap

Этот раздел содержит список перспективных функций для улучшения антидетекта и управления профилями. Все функции описаны на русском и английском языках в формате UTF-8 для корректного чтения AI-парсерами.

This section contains a list of perspective features to improve anti-detection and profile management. All features are described in Russian and English in UTF-8 format for correct reading by AI parsers.

### Расширенный антидетект / Advanced Anti-Detection

- Canvas Fingerprint Spoofing - подмена canvas отпечатка браузера для защиты от трекинга
- Canvas Fingerprint Spoofing - replace browser canvas fingerprint for tracking protection

- WebGL Fingerprint Protection - изменение WebGL параметров рендеринга для анонимности
- WebGL Fingerprint Protection - modify WebGL rendering parameters for anonymity

- Audio Context Noise - добавление шума в Audio API для защиты от audio fingerprinting
- Audio Context Noise - add noise to Audio API for audio fingerprinting protection

- Font Fingerprint Protection - управление списком доступных шрифтов для каждого профиля
- Font Fingerprint Protection - manage available fonts list for each profile

- Hardware Fingerprint Masking - подмена информации о железе процессор видеокарта память
- Hardware Fingerprint Masking - spoof hardware information CPU GPU memory

- Screen Resolution Randomization - случайное разрешение экрана и размер окна
- Screen Resolution Randomization - random screen resolution and window size

- Battery API Spoofing - подмена данных Battery Status API
- Battery API Spoofing - spoof Battery Status API data

- Media Devices Protection - управление списком камер и микрофонов
- Media Devices Protection - manage cameras and microphones list

- WebRTC IP Leak Prevention - блокировка утечки реального IP через WebRTC
- WebRTC IP Leak Prevention - block real IP leak via WebRTC

- Client Rects Randomization - изменение геометрии элементов для защиты от fingerprinting
- Client Rects Randomization - modify element geometry for fingerprinting protection

### Управление прокси / Proxy Management

- Proxy Chain Support - поддержка цепочек прокси для дополнительной анонимности
- Proxy Chain Support - support proxy chains for additional anonymity

- Automatic Proxy Rotation - автоматическая ротация прокси по расписанию или условиям
- Automatic Proxy Rotation - automatic proxy rotation by schedule or conditions

- Proxy Health Monitoring - мониторинг здоровья прокси и автозамена неработающих
- Proxy Health Monitoring - monitor proxy health and auto-replace failed ones

- Proxy Speed Testing - проверка скорости прокси с приоритизацией быстрых
- Proxy Speed Testing - test proxy speed with prioritization of fast ones

- GeoIP Database Integration - интеграция базы GeoIP для точного определения локации
- GeoIP Database Integration - integrate GeoIP database for precise location detection

- Proxy Provider API Integration - интеграция API популярных провайдеров прокси
- Proxy Provider API Integration - integrate API of popular proxy providers

### Управление профилями / Profile Management

- Profile Templates - шаблоны профилей с предустановленными настройками
- Profile Templates - profile templates with preset configurations

- Profile Import Export - экспорт и импорт профилей в JSON формате
- Profile Import Export - export and import profiles in JSON format

- Profile Groups - группировка профилей по проектам или задачам
- Profile Groups - group profiles by projects or tasks

- Profile Cloning - быстрое клонирование существующих профилей
- Profile Cloning - quick cloning of existing profiles

- Profile Notes - добавление заметок и тегов к профилям
- Profile Notes - add notes and tags to profiles

- Profile Statistics - статистика использования профилей время сессий количество запусков
- Profile Statistics - usage statistics session time launch count

- Profile Sync - синхронизация профилей между устройствами через облако
- Profile Sync - synchronize profiles between devices via cloud

### Автоматизация / Automation

- Selenium Integration - интеграция Selenium для автоматизации действий в браузере
- Selenium Integration - integrate Selenium for browser action automation

- Playwright Support - поддержка Playwright как альтернативы Selenium
- Playwright Support - support Playwright as Selenium alternative

- Macro Recording - запись макросов действий пользователя для повтора
- Macro Recording - record user action macros for replay

- Script Scheduler - планировщик выполнения скриптов по расписанию
- Script Scheduler - schedule script execution by time

- API Server Mode - режим API сервера для удаленного управления
- API Server Mode - API server mode for remote control

- Webhook Support - отправка webhook уведомлений о событиях
- Webhook Support - send webhook notifications about events

### Безопасность и приватность / Security and Privacy

- Cookie Management - расширенное управление cookies импорт экспорт чистка
- Cookie Management - advanced cookie management import export cleanup

- Local Storage Control - контроль Local Storage и Session Storage
- Local Storage Control - control Local Storage and Session Storage

- Extension Management - управление расширениями Chrome для каждого профиля
- Extension Management - manage Chrome extensions for each profile

- Password Manager Integration - интеграция с менеджерами паролей
- Password Manager Integration - integrate with password managers

- Encrypted Profiles - шифрование данных профилей паролем
- Encrypted Profiles - encrypt profile data with password

- Stealth Mode - режим максимальной скрытности с отключением логов
- Stealth Mode - maximum stealth mode with logs disabled

### Интерфейс и удобство / Interface and Usability

- Dark Theme - темная тема интерфейса
- Dark Theme - dark interface theme

- Multi-Language Support - поддержка множественных языков интерфейса
- Multi-Language Support - support multiple interface languages

- Quick Actions Menu - меню быстрых действий для профилей
- Quick Actions Menu - quick actions menu for profiles

- Search and Filter - поиск и фильтрация профилей по параметрам
- Search and Filter - search and filter profiles by parameters

- Hotkeys Support - горячие клавиши для основных действий
- Hotkeys Support - hotkeys for main actions

- Profile Status Indicators - индикаторы состояния профилей онлайн офлайн ошибка
- Profile Status Indicators - profile status indicators online offline error

- System Tray Integration - работа из системного трея с минимизацией
- System Tray Integration - work from system tray with minimization

### Мониторинг и логирование / Monitoring and Logging

- Activity Logs - детальные логи активности профилей
- Activity Logs - detailed profile activity logs

- Resource Usage Monitor - мониторинг использования CPU RAM сети
- Resource Usage Monitor - monitor CPU RAM network usage

- Error Tracking - отслеживание и логирование ошибок
- Error Tracking - track and log errors

- Session Recording - запись сессий браузера для анализа
- Session Recording - record browser sessions for analysis

- Analytics Dashboard - панель аналитики с графиками и статистикой
- Analytics Dashboard - analytics dashboard with charts and statistics

### Интеграции / Integrations

- Docker Support - запуск профилей в Docker контейнерах
- Docker Support - run profiles in Docker containers

- Cloud Storage Integration - интеграция с облачными хранилищами Google Drive Dropbox
- Cloud Storage Integration - integrate with cloud storage Google Drive Dropbox

- Captcha Solver Integration - интеграция сервисов решения капчи 2Captcha AntiCaptcha
- Captcha Solver Integration - integrate captcha solving services 2Captcha AntiCaptcha

- SMS Activation Services - интеграция сервисов аренды номеров для SMS
- SMS Activation Services - integrate phone number rental services for SMS

- Database Export - экспорт данных в базы данных MySQL PostgreSQL SQLite
- Database Export - export data to databases MySQL PostgreSQL SQLite

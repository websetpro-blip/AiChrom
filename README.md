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
- Chromium не принимает креды в `--proxy-server`. Для аутентификации мы генерируем Manifest V3 расширение
  per-profile, которое устанавливает `chrome.proxy.settings` и обрабатывает `onAuthRequired` через `webRequest`/`webRequestAuthProvider`.
- Для SOCKS прокси добавляем `--host-resolver-rules="MAP * ~NOTFOUND, EXCLUDE <proxy_host>"` чтобы избежать утечек DNS.

Quick manual test

1. Запусти профиль через AiChrome.
2. В запущенном окне открой `chrome://extensions`, включи Developer mode и проверь background service worker расширения (Inspect) при проблемах.
3. Проверь IP: `https://api.ipify.org?format=json` и гео: `http://ip-api.com/json`.

Автоматизировано

- При запуске AiChrome автоматически генерируется расширение в `extensions/proxy_<profileId>` и передаётся через `--load-extension`.
- Перед запуском выполняется self-test (ipify+ip-api); при провале используется PAC-файл через `--proxy-pac-url`.

Если хочешь, могу оформить PR с отдельной веткой и CI для линтинга — скажи "create PR".

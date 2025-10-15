@echo off
set CHROME="C:\Program Files\Google\Chrome\Application\chrome.exe"
if not exist %CHROME% set CHROME="C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
set PDIR=C:\AI\AiChrome\profiles\_test
mkdir "%PDIR%" >nul 2>&1
%CHROME% --user-data-dir="%PDIR%" --lang=ru-RU --window-size=1280,800 https://example.com

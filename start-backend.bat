@echo off
cd /d C:\AI\AiChrome\api
set CHROME_PATH=C:\Program Files\Google\Chrome\Application\chrome.exe
py -3 -m pip install -r requirements.txt
py -3 -m uvicorn api:app --host 127.0.0.1 --port 8765 --reload
pause

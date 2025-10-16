@echo off
python -m pip install --upgrade pip
pip install -r requirements.txt
pyinstaller --clean AiChrome.spec
echo Done. EXE в папке dist\
pause

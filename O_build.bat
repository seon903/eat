@echo off
REM 윈도우 PC에서 직접 빌드할 때 (Python 3.10+ 필요)
pip install -r requirements.txt pyinstaller
pyinstaller --noconfirm --onefile --windowed --name EatNotifier main.py
echo.
echo dist\EatNotifier.exe 가 생성되었습니다.
pause

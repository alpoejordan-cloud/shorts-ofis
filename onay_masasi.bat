@echo off
REM Çift tıkla: onay masası açılır, tarayıcıda videoları onayla veya reddet.
cd /d "%~dp0"
start "" http://127.0.0.1:8765
.venv\Scripts\python.exe -m ofis onay

@echo off
REM Cift tikla: Shorts Ofis kontrol paneli acilir (http://127.0.0.1:8770). Kapatmak icin bu pencereyi kapat.
cd /d "%~dp0"
.venv\Scripts\python.exe -m ofis panel
pause

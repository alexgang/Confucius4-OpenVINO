@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONUTF8=1
start "" "C:\Users\Trekker-PTL\confucius4-openvino\.venv\Scripts\pythonw.exe" "%~dp0live_caption_app.py" %*

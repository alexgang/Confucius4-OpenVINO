@echo off
cd /d "%~dp0"
set PYTHONUTF8=1
"C:\Users\Trekker-PTL\confucius4-openvino\.venv\Scripts\python.exe" live_caption_app.py --engine %1 --file test_en_60s.wav --autostart --selftest 35 --selftest-out "%~dp0selftest" > "%~dp0selftest_%1.log" 2>&1

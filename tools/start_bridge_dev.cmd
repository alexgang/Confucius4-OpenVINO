@echo off
rem v0.3.9 dev launcher (GUI): engines from the v2.4 package, bridge code from live_dub_ext
cd /d "%~dp0.."
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "EXT_APP_ROOT=C:\Users\Trekker-PTL\Confucius4_LiveCaption_v2.4"
set "EXT_APP_SEARCH_ROOT=C:\Users\Trekker-PTL\Confucius4_LiveCaption_v2.4"
set "PYTHONPATH=%CD%;%CD%\.runtime_deps;%PYTHONPATH%"
"C:\Users\Trekker-PTL\Confucius4_LiveCaption_v2.4\python\python.exe" "%CD%\tools\ext_launcher.py"
if errorlevel 1 pause
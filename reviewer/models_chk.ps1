$m = "C:\Users\Trekker-PTL\confucius4-openvino\models"
foreach ($x in "ov-int4-lmhead-past", "ov-int8-past", "ov-encoder-segment-reviewer", "ov-encoder-segment-reviewer-int4", "qwen3-lm-int8sym-cleanie-ov", "c089_int4\R4") { "$x " + (Test-Path (Join-Path $m $x)) }
"--- c089_int4"; Get-ChildItem (Join-Path $m "c089_int4") -ErrorAction SilentlyContinue | % Name
"--- cleanie"; Get-ChildItem (Join-Path $m "qwen3-lm-int8sym-cleanie-ov") -ErrorAction SilentlyContinue | % { "$($_.Length) $($_.Name)" }
"--- R4"; Get-ChildItem (Join-Path $m "c089_int4\R4") -ErrorAction SilentlyContinue | % { "$($_.Length) $($_.Name)" }
"--- mic"; & "C:\Users\Trekker-PTL\confucius4-openvino\.venv\Scripts\python.exe" -c "import sys; sys.stdout.reconfigure(encoding='utf-8'); import sounddevice as sd; print(sd.query_devices())"
"--- session"; Get-CimInstance Win32_Process -Filter "Name='explorer.exe'" | % { "explorer pid=$($_.ProcessId) session=$($_.SessionId)" }

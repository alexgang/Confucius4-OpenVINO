$d = "C:\Users\Trekker-PTL\WorkBuddy\Worktrees\confucius4-openvino\c038-v2-ir-6c123954"
Get-ChildItem $d -File -Filter *.py | ? { $_.Name -match 'mic|app|backend|seg_stream|streaming|cuda|audiocpp|vad|delivery' } | % { "$($_.Length) $($_.LastWriteTime.ToString('MM-dd HH:mm')) $($_.Name)" }
"--- cuda bits"
Get-ChildItem $d -Recurse -Depth 2 -File -Include *.exe,*.gguf -ErrorAction SilentlyContinue | % { "$($_.Length) $($_.FullName.Substring($d.Length+1))" } | select -First 20
"--- home dirs"
Get-ChildItem "C:\Users\Trekker-PTL" -Directory | % { $_.Name }
"--- models"
Get-ChildItem "$d\models" -Directory -ErrorAction SilentlyContinue | % { $_.Name }
"--- pip"
& "C:\Users\Trekker-PTL\confucius4-openvino\.venv\Scripts\python.exe" -c "import importlib.util as u;print({m: bool(u.find_spec(m)) for m in ['sounddevice','pyaudio','PySide6','PyQt5','tkinter','webrtcvad','silero_vad','soundfile','openvino','openvino_genai','torch']})"

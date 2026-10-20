Set-Location "C:\Users\Trekker-PTL\WorkBuddy\Worktrees\confucius4-openvino\c038-v2-ir-6c123954"
"hits:"; git grep -l -I "Intel123" HEAD 2>&1 | select -First 20
"files:"; (git ls-files | Measure-Object).Count
"remote:"; git remote -v
"shared files touched in 2f79e0e:"; git show --stat --format="" 2f79e0e -- seg_stream.py streaming_asr.py backends.py segment_encoder_backend.py transcribe_stream.py 2>&1

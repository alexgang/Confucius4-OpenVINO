$d = "C:\Users\Trekker-PTL\WorkBuddy\Worktrees\confucius4-openvino\c038-v2-ir-6c123954"
$c = "C:\Users\Trekker-PTL\confucius4-r2t2"
"--- stdout seg_000 (head)"
Get-Content "$d\reports\cuda\logs_stream\seg_000.stdout" -TotalCount 40 -ErrorAction SilentlyContinue
"--- cuda dir"
Get-ChildItem $c -ErrorAction SilentlyContinue | % { $_.Name }
Get-ChildItem "$c\models" -ErrorAction SilentlyContinue | % { "$($_.Length) $($_.Name)" }
"--- help"
& "$c\audio.cpp\audiocpp_cli.exe" --help 2>&1 | select -First 120

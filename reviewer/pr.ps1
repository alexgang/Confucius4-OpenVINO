Get-Process -Id 21376,28756 -ErrorAction SilentlyContinue | select Id,StartTime,@{n='cpu_s';e={[int]$_.CPU}},@{n='ws_mb';e={[int]($_.WorkingSet64/1MB)}} | ft -a | Out-String
$d="C:\Users\Trekker-PTL\WorkBuddy\Worktrees\confucius4-openvino\c038-v2-ir-6c123954"
Get-ChildItem "$d\reports\c089_int4" -File | sort LastWriteTime | select -Last 4 Name,Length,LastWriteTime | ft -a | Out-String
Get-ChildItem "$d" -Filter "*c089*log*" -Recurse -Depth 2 -File -ErrorAction SilentlyContinue | % { $_.FullName; Get-Content $_.FullName -Tail 5 }

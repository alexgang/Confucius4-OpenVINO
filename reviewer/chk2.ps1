$d="C:\Users\Trekker-PTL\WorkBuddy\Worktrees\confucius4-openvino\c038-v2-ir-6c123954\reports"
Get-ChildItem "$d" -Recurse -File | ? {$_.Name -match 'guard' -and $_.LastWriteTime -gt (Get-Date).AddHours(-3)} | % { $_.FullName; $_.LastWriteTime }

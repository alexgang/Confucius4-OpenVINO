$W='C:\Users\Trekker-PTL\WorkBuddy\Worktrees\confucius4-openvino\c038-v2-ir-6c123954'
Get-ChildItem "$W\reports" -Recurse -File -ErrorAction SilentlyContinue | Where-Object { $_.LastWriteTime -gt (Get-Date '2026-10-16 10:40') -and $_.Extension -in '.txt','.json' } |
  Sort-Object LastWriteTime -Descending | Select-Object -First 20 LastWriteTime,Length,@{n='F';e={$_.FullName.Replace("$W\reports\",'')}} | Format-Table -AutoSize

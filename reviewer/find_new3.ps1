Get-ChildItem -Path C:\Users\Trekker-PTL\WorkBuddy\Worktrees\confucius4-openvino\c038-v2-ir-6c123954 -Recurse -File -ErrorAction SilentlyContinue |
  Where-Object { $_.LastWriteTime -gt (Get-Date '2026-10-16 07:00') -and $_.FullName -notlike '*ov_cache*' -and $_.FullName -notlike '*\.git\*' -and $_.Extension -ne '.bin' } |
  Sort-Object LastWriteTime -Descending | Select-Object -First 30 LastWriteTime,Length,@{n='F';e={$_.FullName.Replace('C:\Users\Trekker-PTL\WorkBuddy\Worktrees\confucius4-openvino\c038-v2-ir-6c123954\','')}} | Format-Table -AutoSize -Wrap

$W='C:\Users\Trekker-PTL\WorkBuddy\Worktrees\confucius4-openvino\c038-v2-ir-6c123954'
Get-ChildItem "$W\reports" -Recurse -File -ErrorAction SilentlyContinue | Where-Object { $_.Name -match 'mem' -and $_.Extension -eq '.json' } | Select-Object LastWriteTime,Length,@{n='F';e={$_.FullName.Replace("$W\reports\",'')}} | Format-Table -AutoSize

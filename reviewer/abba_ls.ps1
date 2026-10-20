$W='C:\Users\Trekker-PTL\WorkBuddy\Worktrees\confucius4-openvino\c038-v2-ir-6c123954'
Get-ChildItem "$W\reports\c062_abba" -Recurse -File -ErrorAction SilentlyContinue | Sort-Object LastWriteTime | Select-Object LastWriteTime,Length,@{n='F';e={$_.FullName.Replace("$W\reports\c062_abba\",'')}} | Format-Table -AutoSize

$d = "C:\Users\Trekker-PTL\WorkBuddy\Worktrees\confucius4-openvino\c038-v2-ir-6c123954"
$skip = 'npu_cache|ov_cache|\\models\\'
Get-Date
Get-ChildItem "$d\.workbuddy\memory" | sort LastWriteTime | select -Last 3 | % { "$($_.Name) $($_.LastWriteTime) $($_.Length)" }
"--- reports (last 18h)"
Get-ChildItem "$d\reports" -Recurse -File | ? { $_.LastWriteTime -gt (Get-Date).AddHours(-18) -and $_.FullName -notmatch $skip } | sort LastWriteTime | % { "$($_.LastWriteTime.ToString('MM-dd HH:mm')) $($_.Length) $($_.FullName.Substring($d.Length+1))" }
"--- code/status (last 18h)"
Get-ChildItem "$d" -File -Recurse -Depth 1 -Include *.py,*.md,*.sh,*.txt | ? { $_.LastWriteTime -gt (Get-Date).AddHours(-18) -and $_.FullName -notmatch ($skip + '|\\reports\\') } | sort LastWriteTime | % { "$($_.LastWriteTime.ToString('MM-dd HH:mm')) $($_.Length) $($_.FullName.Substring($d.Length+1))" }
"--- git"
Set-Location $d
git status --short 2>&1 | select -First 40
git log --oneline -8 2>&1
"--- procs"
Get-CimInstance Win32_Process -Filter "Name='python.exe'" | % { "$($_.ProcessId) " + $_.CommandLine.Substring(0, [Math]::Min(160, $_.CommandLine.Length)) }

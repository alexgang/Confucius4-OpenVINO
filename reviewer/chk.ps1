$d="C:\Users\Trekker-PTL\WorkBuddy\Worktrees\confucius4-openvino\c038-v2-ir-6c123954"
Get-Date
(Get-Item "$d\.workbuddy\memory\*.md").LastWriteTime
Get-ChildItem "$d\reports" -Recurse -File | ? {$_.LastWriteTime -gt (Get-Date).AddMinutes(-40)} | select -First 15 Name,LastWriteTime | ft -a | Out-String
Get-CimInstance Win32_Process -Filter "Name='python.exe'" | % { "$($_.ProcessId) " + $_.CommandLine.Substring(0,[Math]::Min(160,$_.CommandLine.Length)) }
Select-String -Path "$d\status\STATUS.md" -Pattern "NPU|ABBA|数据齐备" | select -Last 4 | % {$_.Line.Substring(0,[Math]::Min(160,$_.Line.Length))}

$d="C:\Users\Trekker-PTL\WorkBuddy\Worktrees\confucius4-openvino\c038-v2-ir-6c123954"
foreach ($p in "$d\reports\c089_int4", "$d\models\c089_int4") { "== $p"; if (Test-Path $p) { Get-ChildItem $p -Recurse -File | ? { $_.LastWriteTime -gt (Get-Date).AddHours(-1.5) } | % { "$($_.LastWriteTime.ToString('HH:mm')) $($_.Length) $($_.FullName.Substring($d.Length+1))" } } }
Get-ChildItem $d -Filter "c089c_R4*.log" | % { $_.Name; Get-Content $_.FullName -Tail 6 }

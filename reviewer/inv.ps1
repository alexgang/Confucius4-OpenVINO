$W='C:\Users\Trekker-PTL\WorkBuddy\Worktrees\confucius4-openvino\c038-v2-ir-6c123954'
$M='C:\Users\Trekker-PTL\confucius4-openvino'
foreach ($d in @("$W\reports\cuda","$W\reports\cuda_q4","$W\reports\c053_quant","$W\reports\c053_int4","$W\reports\c053_61min_int4","$M\reports\cuda")) {
  "=== $d"
  Get-ChildItem $d -Recurse -File -ErrorAction SilentlyContinue | Where-Object { $_.Extension -in '.txt','.json','.csv','.log' -and $_.Length -lt 3000000 } |
    Select-Object @{n='F';e={$_.FullName.Replace($d,'')}}, Length, LastWriteTime | Format-Table -AutoSize -HideTableHeaders | Out-String -Width 200
}
"=== scripts"
Get-ChildItem $W -Filter 'c05*cuda*' -File | Select-Object Name,Length | Format-Table -AutoSize -HideTableHeaders | Out-String -Width 200
Get-ChildItem $W -Filter 'cuda_*' -File | Select-Object Name,Length | Format-Table -AutoSize -HideTableHeaders | Out-String -Width 200

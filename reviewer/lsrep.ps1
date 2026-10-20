$W='C:\Users\Trekker-PTL\WorkBuddy\Worktrees\confucius4-openvino\c038-v2-ir-6c123954'
foreach ($d in 'reports\c053_61min_int4','reports\c053_int4','reports\c057_61min_encoder','reports\c048_61min_adaptive') {
  "== $d"; Get-ChildItem "$W\$d" -File -ErrorAction SilentlyContinue | Select-Object Name,Length,LastWriteTime | Format-Table -AutoSize
}

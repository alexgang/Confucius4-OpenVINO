$m = "C:\Users\Trekker-PTL\confucius4-openvino\models"
Get-ChildItem $m -Directory | ? { $_.Name -match 'encoder' } | % {
  $x = Join-Path $_.FullName 'openvino_encoder_model.xml'
  $b = Join-Path $_.FullName 'openvino_encoder_model.bin'
  $n4 = 0; $n8 = 0
  if (Test-Path $x) { $t = Get-Content $x -Raw; $n4 = ([regex]::Matches($t, 'element_type="[ui]4"')).Count; $n8 = ([regex]::Matches($t, 'element_type="[ui]8"')).Count }
  "{0}  bin={1:N0}MB  i4/u4={2}  i8/u8={3}" -f $_.Name, ((Get-Item $b -ErrorAction SilentlyContinue).Length / 1MB), $n4, $n8
}
$w = "C:\Users\Trekker-PTL\WorkBuddy\Worktrees\confucius4-openvino\c038-v2-ir-6c123954\reports"
Get-ChildItem $w -Filter "*enc*int8*" -Recurse -File -ErrorAction SilentlyContinue | select -First 8 | % { $_.FullName.Substring($w.Length + 1) }

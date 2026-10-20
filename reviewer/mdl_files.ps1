$m = "C:\Users\Trekker-PTL\confucius4-openvino\models"
foreach ($x in "ov-encoder-segment-reviewer", "ov-encoder-segment-reviewer-int8asym", "ov-encoder-segment-reviewer-int4", "ov-int8-past", "ov-int4-lmhead-past") {
  "== $x"
  Get-ChildItem (Join-Path $m $x) -File | % { "{0,12} {1}" -f $_.Length, $_.Name }
}

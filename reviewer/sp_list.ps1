$sp = "C:\Users\Trekker-PTL\confucius4-openvino\.venv\Lib\site-packages"
Get-Content "C:\Users\Trekker-PTL\confucius4-openvino\.venv\pyvenv.cfg"
$py = "C:\Users\Trekker-PTL\AppData\Local\Programs\Python\Python312"
"base python size MB: " + [int]((Get-ChildItem $py -Recurse -File -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum / 1MB)
Test-Path "$py\tcl"; Test-Path "$py\DLLs\_tkinter.pyd"
Get-ChildItem $sp -Directory | % {
  $s = (Get-ChildItem $_.FullName -Recurse -File -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum
  [pscustomobject]@{ n = $_.Name; mb = [int]($s / 1MB) }
} | sort mb -Descending | select -First 45 | % { "{0,6} {1}" -f $_.mb, $_.n }
"7z: " + (Test-Path "C:\Program Files\7-Zip\7z.exe")
tar --version

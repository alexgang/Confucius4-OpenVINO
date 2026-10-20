Get-CimInstance Win32_PnPSignedDriver | Where-Object { $_.DeviceName -match 'NPU|Neural|AI Boost' -or $_.DeviceID -match 'VEN_8086&DEV_(643E|7D1D|AD1D|B03E)' } |
  Select-Object DeviceName,DriverVersion,DriverDate,Manufacturer | Format-List
"--- openvino/genai 版本(只读 pip 元数据)"
& 'C:\Users\Trekker-PTL\confucius4-openvino\.venv\Scripts\pip.exe' list --format=freeze 2>$null | Select-String -Pattern '^(openvino|nncf|optimum|transformers|numpy)'

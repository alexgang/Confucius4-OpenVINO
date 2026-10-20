Get-ChildItem -Path C:\Users\Trekker-PTL\confucius4-openvino -Recurse -File -ErrorAction SilentlyContinue |
  Where-Object { $_.LastWriteTime -gt (Get-Date '2026-10-13 12:25') -and $_.FullName -notlike '*ov_cache*' -and $_.FullName -notlike '*\.venv\*' -and $_.FullName -notlike '*\.git\*' -and $_.Extension -ne '.bin' } |
  Sort-Object LastWriteTime -Descending | Select-Object -First 40 LastWriteTime,Length,FullName | Format-Table -AutoSize -Wrap

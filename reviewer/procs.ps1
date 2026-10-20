Get-CimInstance Win32_Process -Filter "Name='python.exe'" | ForEach-Object {
  "{0}  WS={1:N0}MB  start={2}`n    {3}" -f $_.ProcessId, ($_.WorkingSetSize/1MB), $_.CreationDate, $_.CommandLine
}

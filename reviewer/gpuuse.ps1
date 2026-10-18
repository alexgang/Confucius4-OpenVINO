$s = (Get-Counter '\GPU Engine(*)\Utilization Percentage' -SampleInterval 1 -MaxSamples 5).CounterSamples
$s | Where-Object { $_.CookedValue -gt 0.5 } | ForEach-Object {
  if ($_.InstanceName -match 'pid_(\d+)_luid_(0x[0-9A-Fa-f]+_0x[0-9A-Fa-f]+)_phys_\d+_eng_\d+_engtype_(\w+)') {
    [pscustomobject]@{ PID=[int]$Matches[1]; LUID=$Matches[2]; Eng=$Matches[3]; Util=$_.CookedValue }
  }
} | Group-Object PID,LUID,Eng | ForEach-Object {
  $f=$_.Group[0]; $m=($_.Group | Measure-Object Util -Average).Average
  $name=(Get-Process -Id $f.PID -ErrorAction SilentlyContinue).ProcessName
  "{0,6} {1,-16} {2,-12} {3,-8} avg={4:N1}% " -f $f.PID,$name,$f.LUID.Substring(0,12),$f.Eng,$m
} | Sort-Object
"--- rt-translator log tail ---"
Get-ChildItem C:\Users\Trekker-PTL\.openvino\log -Filter 'rt-translator-client-*.log' | Sort-Object LastWriteTime -Descending | Select-Object -First 1 | ForEach-Object { $_.FullName; Get-Content $_.FullName -Tail 6 -Encoding UTF8 }

# 🔴 APP-132/133：v2.6 整链（一次持锁到底）后台启动器
#
# 纪律：
# - 用 **schtasks** 起（不 nohup、不 & ⇒ 不会变成孤儿进程）；
# - 长作业包装器**在脚本内**重定向（`& script *> $log`）—— 🔴 schtasks
#   **不接受 `>` 重定向**（会秒退且无输出）；
# - 起来后**立刻**把 PID 交给 `session_lease.py addpid`（⇒ 新会话拿到 BUSY，
#   不会重复启动同一个作业）；
# - 日志落在 `results/app/app133_chain_runner.log`。
$ErrorActionPreference = 'Continue'
$repo = 'C:\Users\Trekker-PTL\confucius4-openvino'
$py = 'C:\Users\Trekker-PTL\Confucius4_LiveCaption_v2.6\python\python.exe'
$log = Join-Path $repo 'results\app\app133_chain_runner.log'
$script = Join-Path $repo 'results\app\_app133_chain_v26.py'

Set-Location $repo
"=== chain started $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') ===" | Out-File -FilePath $log -Encoding utf8

$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'

# 🔴 包装器：把 stdout/stderr 全部收进 $log（schtasks 不接受 `>` 重定向）
$wrapper = Join-Path $env:TEMP 'app133_chain_wrapper.ps1'
@"
`$ErrorActionPreference = 'Continue'
Set-Location '$repo'
& '$py' -X utf8 '$script' --arms off,on,clone --port 8775 *>> '$log'
"@ | Out-File -FilePath $wrapper -Encoding utf8

$p = Start-Process -FilePath 'powershell.exe' `
    -ArgumentList '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $wrapper `
    -WindowStyle Hidden -PassThru
"PID=$($p.Id)" | Out-File -FilePath $log -Append -Encoding utf8
Write-Output ("CHAIN_PID=" + $p.Id)

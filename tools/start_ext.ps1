# start_ext.ps1 - desktop entry for the live dub bridge launcher.
# Resolves the LiveCaption App python AT RUNTIME (no version is hardcoded):
#   newest  <home>\Confucius4_LiveCaption_v<N.N...>  that has app\, models\, python\pythonw.exe
#   (same rule as ext/app_root.py; MiniMVP / rc dirs never match). EXT_APP_ROOT overrides.
# On failure it shows its own message box and writes %LOCALAPPDATA%\live_dub_ext\launcher_entry.log.
param([switch]$DryRun)
$ErrorActionPreference = 'Stop'
$repo   = Split-Path -Parent $PSScriptRoot
$logDir = Join-Path $env:LOCALAPPDATA 'live_dub_ext'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$log    = Join-Path $logDir 'launcher_entry.log'
function Log($m) { Add-Content -Path $log -Encoding UTF8 -Value ("{0}  {1}" -f (Get-Date -Format s), $m) }
function Fail($m) {
    Log "FAIL $m"
    Add-Type -AssemblyName System.Windows.Forms
    [System.Windows.Forms.MessageBox]::Show("$m`n`n日志：$log", '实时配音桥接 - 启动失败', 'OK', 'Error') | Out-Null
    exit 1
}
try {
    $root = $null
    if ($env:EXT_APP_ROOT) {
        if (Test-Path (Join-Path $env:EXT_APP_ROOT 'python\pythonw.exe')) { $root = $env:EXT_APP_ROOT }
        else { Fail "环境变量 EXT_APP_ROOT=$($env:EXT_APP_ROOT) 下没有 python\pythonw.exe" }
    } else {
        $cands = Get-ChildItem -Path $HOME -Directory -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -match '^Confucius4_LiveCaption_v(\d+(\.\d+)*)$' } |
            ForEach-Object { $v = $Matches[1]; if ($v -notmatch '\.') { $v = "$v.0" }
                             [pscustomobject]@{ Dir = $_.FullName; Ver = [version]$v } } |
            Sort-Object Ver -Descending
        foreach ($c in $cands) {
            if ((Test-Path (Join-Path $c.Dir 'app')) -and (Test-Path (Join-Path $c.Dir 'models')) -and
                (Test-Path (Join-Path $c.Dir 'python\pythonw.exe'))) { $root = $c.Dir; break }
        }
        if (-not $root) { Fail "没有找到可用的实时字幕 App（需要 $HOME\Confucius4_LiveCaption_v* 且含 app\、models\、python\pythonw.exe）。请先安装实时字幕 App。" }
    }
    $pyw = Join-Path $root 'python\pythonw.exe'
    if ($DryRun) { Write-Output "RESOLVED $root"; exit 0 }
    $launcher = Join-Path $repo 'tools\ext_launcher.py'
    if (-not (Test-Path $launcher)) { Fail "找不到启动器 $launcher" }
    $env:PYTHONUTF8 = '1'; $env:PYTHONIOENCODING = 'utf-8'
    $p = Start-Process -FilePath $pyw -ArgumentList ('"{0}"' -f $launcher) -WorkingDirectory $repo -PassThru
    Log "OK app=$root pid=$($p.Id)"
    Start-Sleep -Seconds 3
    if ($p.HasExited) { Fail "启动器进程启动后立即退出（退出码 $($p.ExitCode)）。App 目录：$root" }
} catch { Fail "启动异常：$($_.Exception.Message)" }

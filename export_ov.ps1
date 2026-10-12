# export_ov.ps1
# 阶段 1 — optimum-cli 导出 FP16 + INT8 IR
# 用法（在仓库根目录）:  .\export_ov.ps1
$ErrorActionPreference = "Stop"

$here = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $here

$env:HF_ENDPOINT = "https://hf-mirror.com"
$env:HF_HUB_DOWNLOAD_TIMEOUT = "180"

$py = Join-Path $here ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) { throw "venv python not found at $py" }

# 1. 装 optimum-intel CLI
& $py -m pip install --quiet "optimum-intel[openvino,exporters]"

# 2. 导出 FP16
Write-Host "[export] FP16 ..."
& $py -m optimum.cli.export openvino `
    --model "$here\models\hf" `
    --task automatic-speech-recognition `
    --trust-remote-code `
    --weight-format fp16 `
    --library transformers `
    "$here\models\ov-fp16" 2>&1 | Tee-Object -FilePath "$here\status\logs\p1_export_fp16.log"

# 3. 导出 INT8 (权重量化)
Write-Host "[export] INT8 ..."
& $py -m optimum.cli.export openvino `
    --model "$here\models\hf" `
    --task automatic-speech-recognition `
    --trust-remote-code `
    --weight-format int8 `
    --library transformers `
    "$here\models\ov-int8" 2>&1 | Tee-Object -FilePath "$here\status\logs\p1_export_int8.log"

Write-Host "[export] DONE"
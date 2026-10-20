$W='C:\Users\Trekker-PTL\WorkBuddy\Worktrees\confucius4-openvino\c038-v2-ir-6c123954'
Get-ChildItem "$W\reports" -Recurse -File -ErrorAction SilentlyContinue | Where-Object { $_.FullName -match 'c052|win_gpu|ov_vs_cuda|OV_VS_CUDA|c029|cuda_q4|c053_quant|c054_cuda' -and $_.Extension -in '.json','.csv','.md','.log' -and $_.Length -lt 400000 } |
  Select-Object LastWriteTime,Length,@{n='F';e={$_.FullName.Replace("$W\reports\",'')}} | Format-Table -AutoSize

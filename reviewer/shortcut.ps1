$app = "C:\Users\Trekker-PTL\confucius4-openvino\live_caption"
$ws = New-Object -ComObject WScript.Shell
$lnk = $ws.CreateShortcut("C:\Users\Trekker-PTL\Desktop\Confucius4 实时字幕.lnk")
$lnk.TargetPath = "C:\Users\Trekker-PTL\confucius4-openvino\.venv\Scripts\pythonw.exe"
$lnk.Arguments = "`"$app\live_caption_app.py`""
$lnk.WorkingDirectory = $app
$lnk.Description = "Confucius4-R2T2 实时麦克风字幕（Intel GPU / NPU / NVIDIA CUDA）"
$lnk.Save()
schtasks /delete /tn LiveCaptionSelftest /f
Remove-Item "$app\cuda_pipe_probe.py" -ErrorAction SilentlyContinue
Get-ChildItem $app | % { $_.Name }
Test-Path "C:\Users\Trekker-PTL\Desktop\Confucius4 实时字幕.lnk"

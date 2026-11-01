# app215 · APP-059 辅助脚本：读桌面快捷方式的真实目标（COM 回读，判定用仓库 .venv）
import os, json, hashlib, datetime
import win32com.client

DESKTOP = r'C:\Users\Trekker-PTL\Desktop'
NAMES = ['实时配音桥接服务 v2.1.lnk', '实时配音桥接服务 v2.0.lnk', 'Confucius4 实时字幕 v2.1.lnk']
OUT = r'C:\Users\Trekker-PTL\confucius4-openvino\results\app\app215_shortcuts.json'

sh = win32com.client.Dispatch('WScript.Shell')
rows = []
for n in NAMES:
    p = os.path.join(DESKTOP, n)
    if not os.path.isfile(p):
        rows.append({'name': n, 'exists': False})
        continue
    s = sh.CreateShortcut(p)
    raw = open(p, 'rb').read()
    rows.append({
        'name': n,
        'exists': True,
        'target': s.TargetPath,
        'workdir': s.WorkingDirectory,
        'args': s.Arguments,
        'target_exists': os.path.isfile(s.TargetPath),
        'target_in_v21': ('Confucius4_LiveCaption_v2.1' in s.TargetPath) or ('Confucius4_LiveCaption_v2.1' in s.WorkingDirectory),
        'bytes': len(raw),
        'sha256': hashlib.sha256(raw).hexdigest(),
        'mtime': datetime.datetime.fromtimestamp(os.path.getmtime(p)).strftime('%Y-%m-%d %H:%M:%S'),
    })

out = {
    'tool': 'app215_shortcuts',
    'purpose': 'APP-059 ④/⑤：确认桌面上哪些快捷方式存在、指向哪个包；确认 v2.0.lnk 未被删（reviewer 要求保留）',
    'ts': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    'shortcuts': rows,
}
with open(OUT, 'w', encoding='utf-8') as f:
    json.dump(out, f, ensure_ascii=False, indent=2)
print(json.dumps(out, ensure_ascii=False, indent=2))

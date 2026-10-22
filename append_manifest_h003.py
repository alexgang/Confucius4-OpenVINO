"""在 MANIFEST notes 里补上 H-003 术语表的说明，并重算 files/bytes。"""
import json
import os

PKG = r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_v1.3'
MANIFEST = os.path.join(PKG, 'app', 'MANIFEST.json')

H003_NOTE = (
    "v1.3 新增翻译术语表（H-003）：起因是「QS」被模型译错（QS = Qualification Sample "
    "资格样品，既不是 QPS，也不是「击打」）。translator.py 内置芯片/硬件会议场景的"
    "默认术语表（QS→资格样品、ES→工程样品、power on→点亮、tape-out→流片、"
    "share→市场份额、silicon→芯片、milestone→里程碑 等 10 条），"
    "走 Hy-MT2 官方 **Terminology 模板**（先给「参考译法」，再下翻译指令）；"
    "可用环境变量 LIVECAP_MT_GLOSSARY 指向 JSON 文件扩充或覆盖。"
    "命令行参数 --mt-glossary 开启，**默认关闭** —— 开启后 prompt 变长约 +200 token、"
    "延迟会涨。对客户是**可选增强**，关闭时行为与之前完全一致。"
)


def main():
    with open(MANIFEST, 'r', encoding='utf-8') as f:
        data = json.load(f)

    n_files = 0
    n_bytes = 0
    for dirpath, _dirnames, filenames in os.walk(PKG):
        for fn in filenames:
            p = os.path.join(dirpath, fn)
            if os.path.islink(p) and not os.path.exists(p):
                continue
            try:
                n_bytes += os.path.getsize(p)
                n_files += 1
            except OSError:
                pass

    notes = data.get('notes', '')
    if 'H-003' not in notes:
        idx = notes.find('v1.2 ')
        if idx > 0:
            notes = notes[:idx] + H003_NOTE + notes[idx:]
        else:
            notes = H003_NOTE + notes
    data['notes'] = notes
    data['files'] = n_files
    data['bytes'] = n_bytes

    with open(MANIFEST, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=1)

    print('files:', n_files, 'bytes:', n_bytes)
    print('notes len:', len(notes))


if __name__ == '__main__':
    main()

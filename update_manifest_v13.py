"""更新客户包 MANIFEST.json：版本号 → 1.3，files/bytes 重算，notes 追加 v1.3 说明。

只改 version / files / bytes 三个标量字段，notes 保留原有全部历史说明（不删），
在最前面插入 v1.3 段落。packages 列表不动（依赖未变）。
"""
import json
import os

PKG = r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_v1.3'
MANIFEST = os.path.join(PKG, 'app', 'MANIFEST.json')

V13_NOTE = (
    "v1.3 翻译模型替换（C-102）：翻译模型由通用指令模型 Hunyuan-1.8B-Instruct "
    "换成**翻译专用**的 Hy-MT2-1.8B（tencent/Hy-MT2-1.8B，架构同为 hunyuan_v1_dense，"
    "导出/量化链路不变）。换模型的原因是旧模型不是翻译模型：遇专业术语会乱译、"
    "偶尔会输出解释性文字而非译文。包内 models/mt/ 下的两个产物已全部替换 —— "
    "mt2-int4sym-cw-q（约 993 MB，INT4_SYM per-channel，GPU/NPU 通吃，默认使用）与 "
    "mt2-int8sym-cw-q（约 1.7 GB，INT8_SYM per-channel，显存充裕时可选）；"
    "旧的 int4sym-cw-q / int8sym-cw-q 目录已删除。app/translator.py 同步更新："
    "模型目录解析（DEFAULT_MODEL 与 _cw_model 均指向 mt2-* 目录）、"
    "prompt 改为 Hy-MT2 官方 Default Translation 指令模板（**无 system prompt**，"
    "指令与待译文本同放 user 消息，官方模板见 tencent/Hy-MT2-1.8B README）、"
    "带上下文的分支改用官方 Structured Data 模板的简化版、"
    "generation config 去掉旧 Instruct 专用的 </answer> stop_strings（MT2 直接输出译文正文，EOS 自停）。"
    "GUI/CLI 的翻译后端下拉 5 项（自动 / GPU·INT4 / GPU·INT8 / NPU·INT4 / NPU·INT8）"
    "在新版全部可用，--check 逐项报 [ OK ]。实测（hy_bench/bench_mt2.py，7 句 × 3 次取中位）："
    "GPU·INT4 57.9 tok/s / TTFT 35 ms，NPU·INT4 44.0 tok/s / TTFT 292 ms，"
    "GPU·INT8 37.5 tok/s / TTFT 44 ms，NPU·INT8 29.6 tok/s / TTFT 300 ms；"
    "四配置均无空输出、无乱码；GPU·INT4 与 NPU·INT4 输出逐字一致，"
    "INT8 与 INT4 相似度中位 0.966（最低 0.852），差异均为同义改写。"
    "与旧 Instruct 模型相比，MT2 **更快**（INT4 57.9 vs 49.4 tok/s）且译文质量明显更好。"
    "对客户是**透明升级**：界面、配置、命令行参数全部不变，解压新版即可。"
)


def main():
    with open(MANIFEST, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # files / bytes 重算（与 v1.2 口径一致：包根下所有普通文件）
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

    old_ver = data.get('version')
    old_files = data.get('files')
    old_bytes = data.get('bytes')

    data['version'] = '1.3'
    data['files'] = n_files
    data['bytes'] = n_bytes

    notes = data.get('notes', '')
    if not notes.startswith('v1.3'):
        data['notes'] = V13_NOTE + notes

    with open(MANIFEST, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=1)

    print(f'version: {old_ver} -> {data["version"]}')
    print(f'files:   {old_files} -> {n_files}')
    print(f'bytes:   {old_bytes} -> {n_bytes}')
    print(f'notes len: {len(notes)} -> {len(data["notes"])}')


if __name__ == '__main__':
    main()

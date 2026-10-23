"""修正客户包 app/MANIFEST.json 的 notes，并重算 files/bytes。

要修的两处实测不符：
1. v1.3 段落里写「包内 models/mt/ 下的两个产物已全部替换 —— mt2-int4sym-cw-q 与
   mt2-int8sym-cw-q」→ 实际**最终只附带 INT4**（后面的段落已经写了 INT8 被移除，
   但前一段没改，两条自相矛盾）。
2. 「GPU·INT4 与 NPU·INT4 输出逐字一致」→ H-001 的 200 句 wmt24pp 基准已推翻
   （INT4 仅 39/200 逐字相同），只能说质量等价。

另外：新增了 results/（正确率基准 2.5 MB），files/bytes 必须重算。

C-133 / APP-002：files/bytes 的统计口径改为与 `pack_v13.py` **完全一致**
（`pkg_exclude.package_stats`），消除此前「源目录口径 vs zip 内容口径」的漂移。
MANIFEST 自身**不计入**（否则自引用：它写的 bytes 会改变它自己的长度）。
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pkg_exclude  # noqa: E402

PKG = r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_v1.3'
MANIFEST = os.path.join(PKG, 'app', 'MANIFEST.json')
MANIFEST_REL = 'app/MANIFEST.json'

SUBS = [
    (
        '包内 models/mt/ 下的两个产物已全部替换 —— mt2-int4sym-cw-q'
        '（约 993 MB，INT4_SYM per-channel，GPU/NPU 通吃，默认使用）与 '
        'mt2-int8sym-cw-q（约 1.7 GB，INT8_SYM per-channel，显存充裕时可选）；'
        '旧的 int4sym-cw-q / int8sym-cw-q 目录已删除。',
        '包内 models/mt/ 下只剩一个产物：mt2-int4sym-cw-q'
        '（约 993 MB，INT4_SYM per-channel，GPU/NPU 通吃，默认使用）；'
        '旧的 int4sym-cw-q / int8sym-cw-q 目录已删除，'
        'INT8 版本（mt2-int8sym-cw-q）后端可用但**不随包**（见后一条说明）。',
    ),
    (
        'GPU·INT4 与 NPU·INT4 输出逐字一致，INT8 与 INT4 相似度中位 0.966'
        '（最低 0.852），差异均为同义改写。',
        '**更正**：同量化在 GPU 与 NPU 上**并非逐字一致**（200 句 wmt24pp 上 '
        'INT4 仅 39/200、INT8 116/200 逐字相同），只能说**质量等价**'
        '（chrF++ 差 0.1~0.3）；INT8 与 INT4 相似度中位 0.966（最低 0.852），'
        '差异均为同义改写。',
    ),
]

NEW_NOTE = (
    'v1.3 修订（2026-10-22，Hy-MT2 纠偏 H-001~H-004 执行后）：'
    '（1）补齐**正确率基准** —— 200 句 wmt24pp（en→zh 正向、zh→en 反向构造，'
    '因 FLORES 仓库受限；另含 20 句会议口语子集），BF16-CPU / INT8-GPU / INT8-NPU / '
    'INT4-GPU / INT4-NPU 五配置 × 两方向，指标 BLEU + chrF++ + paired bootstrap 95% CI。'
    '结论：**INT4 相对 BF16 掉 1.53~1.81 chrF++**（CI 不含 0、p≈0.001，落在 1.0~2.0 灰区），'
    '**INT8 与 BF16 统计等价**（|Δ|≤0.25，CI 含 0）。完整矩阵与逐句输出随包附在 '
    '`results\\`（mt2_accuracy.md / .json / mt2_acc_outputs/）。'
    '（2）**内存实测**：INT4-CW 常驻约 1.2 GB（集显）/ 1.6 GB（NPU），'
    'INT8-CW 约 2.0 GB / 2.5 GB；BF16 约 7 GB，不建议客户端使用（见 results\\mt2_memory.json）。'
    '（3）IR 目录的 tokenizer_config / generation_config 已覆盖为 HF Hy-MT2 原件，'
    'openvino_tokenizer/detokenizer 从 Hy-MT2 重新生成（H-002）。'
    '（4）新增可选术语表开关 `--mt-glossary`（默认关闭，延迟 +62 ms / +11.6%）（H-003）。'
    '（5）README 中「INT8 随包」「设备不影响输出（逐字一致）」两处表述已更正。'
)


def main():
    with open(MANIFEST, 'r', encoding='utf-8') as f:
        data = json.load(f)

    notes = data.get('notes', '')
    for old, new in SUBS:
        if old not in notes:
            print('!! 未匹配到待替换片段：', old[:40], '…')
            continue
        notes = notes.replace(old, new)
        print('已替换：', old[:28], '…')

    data['notes'] = NEW_NOTE + notes

    # files / bytes 重算 —— 与 pack_v13.py 打包**同一口径**（排除编译缓存等）
    n_files, n_bytes = pkg_exclude.package_stats(PKG, skip=(MANIFEST_REL,))
    print(f'files: {data.get("files")} -> {n_files}')
    print(f'bytes: {data.get("bytes")} -> {n_bytes} ({n_bytes/1024**3:.2f} GB)')
    data['files'] = n_files
    data['bytes'] = n_bytes

    with open(MANIFEST, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print('已写入', MANIFEST)


if __name__ == '__main__':
    main()

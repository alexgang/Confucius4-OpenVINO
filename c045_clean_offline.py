"""c045_clean_offline.py — 从已保存的离线结果 JSON 重新生成 transcript（剥离 "language None<asr_text>" 前缀）

用途: 离线解码时模型会输出 "language None<asr_text>" 前缀（流式路径由
parse_asr_output 剥离, 早期版本的 c045_two_pass.py 漏了）。本脚本不重跑模型,
直接从 reports/spe_61min_offline_*.json 重新生成干净的 .txt。

用法:
  .venv python c045_clean_offline.py reports/spe_61min_offline_ov-mix12-past.json
"""
import os, sys, json, argparse

sys.path.insert(0, '.')
from streaming_asr import parse_asr_output


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('json_path', nargs='+')
    args = ap.parse_args()

    for jp in args.json_path:
        with open(jp, 'r', encoding='utf-8') as f:
            rows = json.load(f)
        out_txt = os.path.splitext(jp)[0] + '.txt'
        n_fixed = 0
        with open(out_txt, 'w', encoding='utf-8') as f:
            for r in rows:
                raw = r.get('text', '')
                _lang, clean = parse_asr_output(raw)
                if clean != raw.strip():
                    n_fixed += 1
                    r['text_raw'] = raw
                    r['text'] = clean
                f.write(f"[{r['start_s']:7.1f}-{r['end_s']:7.1f}] {r['text']}\n")
        with open(jp, 'w', encoding='utf-8') as f:
            json.dump(rows, f, ensure_ascii=False, indent=2)
        print(f'{os.path.basename(jp)}: 剥离前缀 {n_fixed}/{len(rows)} 段 → {out_txt}')


if __name__ == '__main__':
    main()
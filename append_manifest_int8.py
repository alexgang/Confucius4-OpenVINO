"""在 MANIFEST notes 开头插入 v1.3 的「只附带 INT4」补充说明。

放在 v1.3 段落之后、v1.2 历史段落之前 —— 保持时间顺序。
"""
import json
import os

PKG = r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_v1.3'
MANIFEST = os.path.join(PKG, 'app', 'MANIFEST.json')

INT8_NOTE = (
    "v1.3 客户包**只附带 INT4 一个量化版本**：models/mt/mt2-int8sym-cw-q（1.7 GB）"
    "已从包内移除，包体因此减少约 1.8 GB（12.8 GB → 11.0 GB，解压后磁盘占用从约 10 GB "
    "降到约 9 GB）。移除理由：实测 INT8 与 INT4 的译文差异仅为同义改写"
    "（相似度中位 0.966、最低 0.852），而 INT8 多占约 700 MB 显存、速度慢约 33%，"
    "对客户机没有实际收益。开发机 hy_bench/ov/ 下仍保留 INT8 产物供对比测试。"
    "配套代码调整：translator.py 的 _MT_CANDIDATES 增加 bundled 标记（区分"
    "「本包不附带」与「本机缺模型」），live_caption_app.py 的 --check 对不带附带的项"
    "显示 [ — ]（本包不附带该量化版本）而非 [缺 ]（缺模型），避免客户误判为安装故障；"
    "GUI 下拉本身无需改动 —— 客户机上模型目录不存在时该两项自动不出现。"
)


def main():
    with open(MANIFEST, 'r', encoding='utf-8') as f:
        data = json.load(f)

    notes = data.get('notes', '')
    if '只附带 INT4' in notes:
        print('已存在，跳过')
        return

    # 插到 v1.3 段落之后：找 "v1.2 " 的位置（历史段落起点）
    idx = notes.find('v1.2 ')
    if idx > 0:
        notes = notes[:idx] + INT8_NOTE + notes[idx:]
    else:
        notes = INT8_NOTE + notes
    data['notes'] = notes

    with open(MANIFEST, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=1)

    print('notes len:', len(notes))
    print('head:', notes[:100])


if __name__ == '__main__':
    main()

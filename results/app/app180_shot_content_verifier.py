#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""app180 —— 截图**内容有效性**独立复核（APP-051② 的「像素级守卫」补强）。

🔴🔴🔴 **为什么必须有这个脚本（抓到的真实缺陷）**：
  `app178`（pythonw 冷启动）的判据是「色彩数 ≥ 8 ⇒ 不是空白」。
  实测该判据**太弱**：
    - 抓到的 PNG **只有 7 350 B**、**1096×859**、**色彩数 = 66**；
    - 但**人眼一看就是「只有标题栏、客户区全空」**！
  ⇒ 66 种颜色**全部来自标题栏**（边框 + 标题文字 + 最小化/最大化/关闭按钮）
  ⇒ 客户区（控件区）**一个像素都没有**
  ⇒ 「色彩数 ≥ 8」这个判据 **恒真** ⇒ **静默假通过**。
  （MEMORY 铁律：「判据 PASS ≠ 判据正确」⇒ 必须拿**已知有缺陷的产物**跑一遍。）

🔴 **本脚本的判据（能识破上面这个假通过）**：
  ① **客户区**必须**有内容** ⇒ 把标题栏（顶部 ~32 px）裁掉后，
     剩下的区域**色彩数仍须 ≥ 阈值**（空客户区 ⇒ 色彩数 = 1）；
  ② **纵向内容覆盖率**：客户区里「非背景色」的像素**行数占比**须 > 0；
     （全空 ⇒ 0 行）；
  ③ 对照组：**已知有缺陷**的冷启动图（`app178_cold1.png`）⇒ 必须 FAIL；
     **已知有内容**的布局图（`app048_layout_1920x1080.png`）⇒ 必须 PASS
     ⇒ 证明判据有鉴别力（不是恒真）。

🔴 **纪律**：纯只读（只读 PNG）⇒ **不占机器锁、不跑推理**。
"""
from __future__ import annotations

import json
import os
import sys

HOME = r'C:\Users\Trekker-PTL'
HERE = os.path.dirname(os.path.abspath(__file__))

PASS = 0
FAIL = 0
CHECKS = []


def check(name, cond, detail=''):
    global PASS, FAIL
    ok = bool(cond)
    if ok:
        PASS += 1
    else:
        FAIL += 1
    CHECKS.append({'name': name, 'ok': ok, 'detail': str(detail)})
    print('  [%s] %s%s' % ('PASS' if ok else 'FAIL', name,
                           ('  —— %s' % detail) if detail else ''))
    return ok


def analyse(path, title_h=34):
    """返回客户区（裁掉标题栏）的色彩数与非背景行占比。

    🔴🔴🔴 **第一版判据的缺陷（本脚本自己踩到）**：
      最初用「非背景像素**行占比**」当「客户区有内容」的判据
      ⇒ 实测**空客户区**那张图 `content_row_ratio = 1.0`（**判据恒真**！）
      ⇒ 真因：**客户区四周有 1 px 的窗口边框**（颜色 ≠ 背景白）
      ⇒ 每一行都有「非背景像素」⇒ 行占比恒为 1。
      ⇒ 教训：**「行占比」这种粗粒度指标会被边框污染**
      ⇒ 改用**色彩数**（真内容 ⇒ 几十上百种颜色；空客户区 ⇒ 只有边框色 + 底色
      ⇒ **2 种**）⇒ 判据有鉴别力。
    """
    from PIL import Image
    im = Image.open(path).convert('RGB')
    w, h = im.size
    if h <= title_h + 8:
        return {'size': [w, h], 'client_n_colors': 0,
                'content_row_ratio': 0.0, 'full_n_colors': 0}
    client = im.crop((0, title_h, w, h))
    cols = client.getcolors(maxcolors=300000) or []
    # 背景色 = 出现最多的那个（一般是白/浅灰）
    bg = max(cols, key=lambda c: c[0])[1] if cols else None
    n_content_rows = 0
    if cols:
        px = client.load()
        for y in range(client.size[1]):
            row_has = False
            for x in range(0, client.size[0], 2):
                if px[x, y] != bg:
                    row_has = True
                    break
            if row_has:
                n_content_rows += 1
    return {
        'size': [w, h],
        'full_n_colors': len(im.getcolors(maxcolors=300000) or []),
        'client_n_colors': len(cols),
        'content_row_ratio': round(n_content_rows / max(client.size[1], 1), 4),
        'bg': bg,
    }


def main():
    targets = [
        (os.path.join(HOME, 'shared', 'app_pythonw_coldstart',
                      'app178_cold1.png'),
         'app178 pythonw 冷启动图（**已知有缺陷**：客户区全空）',
         False),
        (os.path.join(HOME, 'shared', 'app_pythonw_coldstart',
                      'app178_cold2.png'),
         'app178 pythonw 冷启动图 cold2（已知有缺陷）',
         False),
        (os.path.join(HOME, 'shared', 'app_gui_layout',
                      'app048_layout_1920x1080.png'),
         'app048 布局图 1920x1080（**已知有内容**）',
         True),
        (os.path.join(HOME, 'shared', 'app_gui_layout',
                      'app048_layout_1280x720.png'),
         'app048 布局图 1280x720（已知有内容）',
         True),
    ]

    print('== 客户区内容有效性复核 ==')
    results = []
    for path, desc, expect_ok in targets:
        if not os.path.isfile(path):
            check('存在：%s' % os.path.basename(path), False, path)
            continue
        try:
            a = analyse(path)
        except Exception as e:
            check('分析：%s' % os.path.basename(path), False, repr(e))
            continue
        results.append({'path': path, 'desc': desc, **a})
        print('  · %-52s %s' % (os.path.basename(path), a))
        # 🔴 判据：客户区**色彩数**必须足够多（真内容 ⇒ 几十上百种；
        #   空客户区 ⇒ 只有边框色 + 底色 ⇒ **2 种**）。
        #   ⚠️ 不用「行占比」⇒ 会被 1 px 窗口边框污染（实测恒为 1.0）。
        has_content = a['client_n_colors'] >= 8
        check('客户区有内容：%s' % os.path.basename(path),
              has_content == expect_ok,
              'client_n_colors=%d content_row_ratio=%.4f ⇒ 判定 %s（期望 %s）'
              % (a['client_n_colors'], a['content_row_ratio'],
                 '有内容' if has_content else '空白',
                 '有内容' if expect_ok else '空白'))

    print('\n== 鉴别力自检 ==')
    # 反证：把「有内容」判据退化成旧的「整图色彩数 ≥ 8」⇒ 必须**放行**那张坏图
    #   ⇒ 证明**旧判据恒真**，而新判据能识破它。
    bad = [r for r in results if 'app178' in r['path']]
    old_pass_on_bad = [r for r in bad if r['full_n_colors'] >= 8]
    check('反证：旧判据（整图色彩数 ≥ 8）会**放行**那张空客户区的冷启动图',
          len(old_pass_on_bad) == len(bad) and len(bad) > 0,
          '整图色彩数=%r ⇒ 旧判据恒真 ⇒ 必须换判据'
          % [r['full_n_colors'] for r in bad])
    check('反证：新判据（**客户区**色彩数）**不放行**那张坏图',
          all(r['client_n_colors'] < 8 for r in bad),
          'client_n_colors=%r' % [r['client_n_colors'] for r in bad])
    good = [r for r in results if 'app048' in r['path']]
    check('反证：新判据**放行**有内容的布局图（不是「一律判空」）',
          all(r['client_n_colors'] >= 8 for r in good) and len(good) > 0,
          'client_n_colors=%r' % [r['client_n_colors'] for r in good])

    verdict = 'PASS' if FAIL == 0 else 'FAIL'
    print('\nPASS %d  FAIL %d  verdict=%s' % (PASS, FAIL, verdict))
    ev = {
        'script': os.path.basename(__file__),
        'correction': 'APP-051②（截图判据补强）/ APP-043（pythonw 冷启动）',
        'results': results,
        'checks': CHECKS, 'n_pass': PASS, 'n_fail': FAIL, 'verdict': verdict,
        'finding': 'app178 的「色彩数 ≥ 8」判据**恒真**（66 色全部来自标题栏）'
                   '⇒ pythonw 冷启动图**客户区全空** ⇒ 该图**不能**作为'
                   '「GUI 正常渲染」的证据 ⇒ 需重抓（等 Tk 完成首次布局绘制）。',
    }
    out = os.path.join(HERE, 'app180_shot_content_evidence.json')
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(ev, f, ensure_ascii=False, indent=2)
    print('[evidence] %s' % out)
    return 0 if FAIL == 0 else 1


if __name__ == '__main__':
    sys.exit(main())

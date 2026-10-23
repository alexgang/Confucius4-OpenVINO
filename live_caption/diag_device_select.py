"""APP-004 第 3 条：设备选择的自检脚本。

覆盖：
  1. 实际检测到的设备列表（不含不存在的设备）
  2. 不可用设备 → 回退到推荐默认（**不卡死**）
  3. 优先级：命令行 > 配置文件 > 推荐默认值
  4. 配置持久化：写入 → 读回 → 下次启动恢复
  5. 精度约束：NPU 不支持 f32

跑法（不需要 GPU、不需要模型、不需要机器锁）：
    .venv\\Scripts\\python.exe live_caption\\diag_device_select.py
"""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import device_config as dc

FAILS = []


def check(name, cond, detail=''):
    print(f'  [{"PASS" if cond else "FAIL"}] {name}'
          + (f'  {detail}' if detail else ''))
    if not cond:
        FAILS.append(name)


def main():
    print('== 1. 实际检测 ==')
    avail = dc.available_devices()
    print(f'  可用设备：{avail}')
    check('至少探测到 1 个设备', len(avail) >= 1, str(avail))
    check('探测结果不含空串', all(d for d in avail))

    print('\n== 2. 不可用设备回退 ==')
    for role in ('asr', 'mt', 'tts'):
        dev, note = dc.resolve_device(role, 'NO_SUCH_DEVICE_XYZ', avail)
        check(f'{role}: 不存在的设备能回退', dev in avail or dev == 'CPU',
              f'-> {dev}, note={note}')
        check(f'{role}: 回退有提示', bool(note), str(note))
    # 现有设备应当原样返回
    d0, n0 = dc.resolve_device('asr', avail[0], avail)
    check('可用设备原样返回', d0 == avail[0] and n0 is None, f'{d0} / {n0}')

    print('\n== 3. 优先级：命令行 > 配置 > 默认 ==')
    tmpdir = tempfile.mkdtemp(prefix='devcfg_')
    cfg = os.path.join(tmpdir, 'device_config.json')
    orig_path = dc.CONFIG_PATH
    try:
        dc.CONFIG_PATH = cfg
        # 只有配置文件里有值
        dc.save_config({'asr': 'CPU', 'mt': 'CPU', 'tts': 'CPU'})
        sel, notes = dc.get_devices({})
        check('配置生效', sel['asr'] == 'CPU', str(sel))
        # 命令行覆盖配置
        sel, notes = dc.get_devices({'asr': avail[0]})
        check('命令行覆盖配置', sel['asr'] == avail[0], str(sel))
        # 都没有 → 推荐默认（会被回退到实际可用）
        dc.save_config({})
        sel, notes = dc.get_devices({})
        check('回落到推荐默认', sel['mt'] == dc.DEFAULT_DEVICES['mt'], str(sel))
    finally:
        dc.CONFIG_PATH = orig_path

    print('\n== 4. 配置持久化（真实路径）==')
    saved = dc.save_config({'asr': 'GPU.0', 'mt': 'GPU.0', 'tts': 'NPU'})
    check('写入成功', saved, dc.CONFIG_PATH)
    back = dc.load_config()
    check('读回一致', back.get('tts') == 'NPU', str(back))
    check('配置文件在 LOCALAPPDATA 下',
          'Confucius4LiveCaption' in dc.CONFIG_PATH, dc.CONFIG_PATH)

    print('\n== 5. 精度约束 ==')
    e = dc.check_precision('NPU', 'f32')
    check('NPU + f32 被拒', e is not None, str(e))
    e2 = dc.check_precision('NPU', 'f16')
    check('NPU + f16 通过', e2 is None, str(e2))
    e3 = dc.check_precision('GPU.0', 'f32')
    check('GPU.0 + f32 通过', e3 is None, str(e3))

    print('\n== 6. 损坏的配置文件不崩 ==')
    tmpdir = tempfile.mkdtemp(prefix='devcfg2_')
    bad = os.path.join(tmpdir, 'device_config.json')
    with open(bad, 'w', encoding='utf-8') as f:
        f.write('{ this is not json ')
    orig = dc.CONFIG_PATH
    try:
        dc.CONFIG_PATH = bad
        check('损坏配置返回空字典', dc.load_config() == {}, str(dc.load_config()))
    finally:
        dc.CONFIG_PATH = orig

    print()
    if FAILS:
        print(f'ALL FAIL ({len(FAILS)}): ' + ', '.join(FAILS))
        return 1
    print('ALL PASS')
    return 0


if __name__ == '__main__':
    sys.exit(main())

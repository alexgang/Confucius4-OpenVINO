"""APP-004 第 3 条：设备选择的自检脚本。

覆盖：
  1. 实际检测到的设备列表（不含不存在的设备）
  2. 不可用设备 → 回退到推荐默认（**不卡死**）
  3. 优先级：命令行 > 配置文件 > 推荐默认值
  4. 配置持久化：写入 → 读回 → 下次启动恢复
  5. 精度约束：NPU 不支持 f32

跑法（不需要 GPU、不需要模型、不需要机器锁）：
    .venv\\Scripts\\python.exe live_caption\\diag_device_select.py

🔴🔴 **自检脚本不得写用户的真实配置**（APP-106 §1 / §191）：
   旧实现第 4 节写的是「**真实路径**」⇒ 跑一次自检就把 A 的
   ``%LOCALAPPDATA%\\Confucius4LiveCaption\\device_config.json`` 覆盖成
   ``{asr: GPU.0, mt: GPU.0, tts: NPU}``
   （2026-11-13 15:10:34 实测发生 ⇒ §191 的还原被推翻）
   ⇒ APP-106 §1 要保住的「旧用户配置」现场被毁。
   ⇒ 现在**全程走隔离路径**，收尾断言真实配置的 SHA256 未变。
"""
import hashlib
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


def _sha256(path):
    """文件的 SHA256；文件不存在 ⇒ None（用于「真实配置有没有被改」的断言）。"""
    if not os.path.exists(path):
        return None
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()


def main():
    # 🔴 真实配置路径：全程**只读**，只用来「比对有没有被改」。
    real_path = dc.CONFIG_PATH
    real_sha_before = _sha256(real_path)

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
        # 🔴 `save_config({})` **清不掉**已有的设备键（APP-090②c / APP-104 的
        #   「合并写」语义：空保存只补键、不删键）⇒ 想测「**没有配置文件**」
        #   必须真的把文件拿掉，否则这条断言会拿旧值当「默认」⇒ 假 FAIL
        #   （2026-11-14 实测：改前恒 FAIL `回落到推荐默认`）。
        try:
            os.remove(cfg)
        except FileNotFoundError:
            pass
        sel, notes = dc.get_devices({})
        check('回落到推荐默认', sel['mt'] == dc.DEFAULT_DEVICES['mt'], str(sel))
    finally:
        dc.CONFIG_PATH = orig_path

    print('\n== 4. 配置持久化（隔离路径，不碰真实配置）==')
    # 🔴 旧实现这里写的是**真实路径**（小节标题就叫「配置持久化（真实路径）」）
    #    ⇒ 自检脚本一跑就把用户真实配置覆盖成 {GPU.0, GPU.0, NPU}
    #    （APP-106 §1 / §191 的「旧用户配置」现场由此被毁，2026-11-13 15:10:34 实测）。
    #    现在只写隔离路径，并断言没碰真实配置。
    tmpdir4 = tempfile.mkdtemp(prefix='devcfg3_')
    cfg4 = os.path.join(tmpdir4, 'device_config.json')
    orig_path = dc.CONFIG_PATH
    try:
        dc.CONFIG_PATH = cfg4
        saved = dc.save_config({'asr': 'GPU.0', 'mt': 'GPU.0', 'tts': 'NPU'})
        check('写入成功', saved, cfg4)
        back = dc.load_config()
        check('读回一致', back.get('tts') == 'NPU', str(back))
        check('写的是隔离路径，不是真实配置',
              dc.CONFIG_PATH == cfg4 and dc.CONFIG_PATH != real_path,
              dc.CONFIG_PATH)
    finally:
        dc.CONFIG_PATH = orig_path

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

    # 🔴 收尾断言：用户的**真实配置**必须逐字节没被动过。
    real_sha_after = _sha256(real_path)
    check('真实配置未被本脚本改动', real_sha_before == real_sha_after,
          f'{real_path}: {real_sha_before} -> {real_sha_after}')

    print()
    if FAILS:
        print(f'ALL FAIL ({len(FAILS)}): ' + ', '.join(FAILS))
        return 1
    print('ALL PASS')
    return 0


if __name__ == '__main__':
    sys.exit(main())

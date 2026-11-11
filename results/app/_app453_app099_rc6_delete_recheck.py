# -*- coding: utf-8 -*-
r"""APP-099 第 0 节第 4 条：rc6 删除的**判据复核**（不重跑删除、不占设备）。

背景（判据本体错，不是删除失败）：
  `_app447_app099_rc6_delete.py` 把 `SHFileOperationW` 的 `rc == 0` 当成唯一
  成功条件，并隐含「删完应释放磁盘空间」。但：
    · `FOF_ALLOWUNDO` 送回收站是**同盘元数据移动** ⇒ C 盘可用空间不释放，
      `freed_gb ≈ 0`（甚至因回收站元数据略负）属正常，不是失败；
    · `SHFileOperationW` 返回值是 shell 专用码，rc=2 不等于「目标没删掉」。
  真实成功判据应为：**两个目标不在原位 + 四个保护对象完好 +
  回收站里这两项都能查到 $I 记录且 $R 实体仍在（可逆）**。

本轮第二处判据坑（自查发现）：
  Windows 10 的 `$I` 记录是 8B ver / 8B size / 8B FILETIME /
  **4B 路径字符数** / UTF-16LE 原路径 ⇒ 路径从 **offset 28** 开始。
  初版把 offset 24 当路径起点，只解出长度 DWORD 的低字节（1 个字符），
  于是「回收站零命中」是**假 FAIL**。改对偏移后实测命中 11620 条目录内
  文件 + 1 条 zip。

本脚本只读：枚举 C:\$Recycle.Bin 的 $I 记录 → 定位 rc6 两项 → 重算结论 →
5 组反证。`app438_app099_rc6_delete.json` 原始证据保持 write-once，不改写；
`pass=false` 是旧判据输出，以本文件 `pass_rechecked` 为准。
"""
import datetime
import json
import os
import struct

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, 'app438_app099_rc6_delete.json')
OUT = os.path.join(HERE, 'app453_app099_rc6_delete_recheck.json')
RECYCLE_BIN = 'C:\\' + '$Recycle.Bin'

RC6_DIR = r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_MiniMVP_v1.0-rc6'
RC6_ZIP = r'C:\Users\Trekker-PTL\shared\minimvp\Confucius4_LiveCaption_MiniMVP_v1.0-rc6_perftest.zip'


def parse_i_file(path):
    """解析 $I 记录（Win10 ver=2）：路径从 offset 28 起，长度字段在 offset 24。"""
    b = open(path, 'rb').read()
    if len(b) < 28:
        return None
    ver = struct.unpack_from('<Q', b, 0)[0]
    size = struct.unpack_from('<Q', b, 8)[0]
    ft = struct.unpack_from('<Q', b, 16)[0]
    if ver == 2:
        n = struct.unpack_from('<I', b, 24)[0]
        orig = b[28:28 + 2 * n].decode('utf-16le', 'replace').rstrip('\x00')
    else:
        orig = b[24:24 + 520].decode('mbcs', 'replace').split('\x00')[0]
    try:
        dt = (datetime.datetime(1601, 1, 1)
              + datetime.timedelta(microseconds=ft / 10))
        utc = dt.strftime('%Y-%m-%d %H:%M:%S')
        local = (dt + datetime.timedelta(hours=8)).strftime('%Y-%m-%d %H:%M:%S')
    except Exception:
        utc = local = None
    return {'ver': ver, 'size_bytes': size, 'deleted_utc': utc,
            'deleted_local_utc8': local, 'orig_path': orig}


def scan_recycle_bin():
    """只读统计；不把上万条记录塞进证据 json。"""
    st = {
        'root': RECYCLE_BIN, 'n_i_records_scanned': 0,
        'n_under_rc6_dir': 0, 'n_exact_zip': 0,
        'n_r_exists': 0, 'n_r_missing': 0,
        'dir_samples': [], 'zip_records': [], 'errors': [],
    }
    if not os.path.isdir(RECYCLE_BIN):
        st['errors'].append('回收站根目录不存在')
        return st
    for sid in os.listdir(RECYCLE_BIN):
        d = os.path.join(RECYCLE_BIN, sid)
        if not os.path.isdir(d):
            continue
        try:
            names = os.listdir(d)
        except Exception as e:
            st['errors'].append('%s: %r' % (sid, e))
            continue
        for fn in names:
            if not fn.startswith('$I'):
                continue
            st['n_i_records_scanned'] += 1
            ip = os.path.join(d, fn)
            try:
                rec = parse_i_file(ip)
                if not rec:
                    continue
                low = os.path.normcase(rec['orig_path'])
                is_dir = low.startswith(os.path.normcase(RC6_DIR))
                is_zip = (low == os.path.normcase(RC6_ZIP))
                if not (is_dir or is_zip):
                    continue
                rp = os.path.join(d, '$R' + fn[2:])
                rec['i_file'] = ip
                rec['r_path'] = rp
                rec['r_exists'] = os.path.exists(rp)
                rec['r_isdir'] = os.path.isdir(rp)
                if is_dir:
                    st['n_under_rc6_dir'] += 1
                    if rec['r_exists']:
                        st['n_r_exists'] += 1
                    else:
                        st['n_r_missing'] += 1
                    if len(st['dir_samples']) < 3:
                        st['dir_samples'].append(rec)
                if is_zip:
                    st['n_exact_zip'] += 1
                    st['zip_records'].append(rec)
            except Exception as e:
                st['errors'].append('%s: %r' % (fn, e))
    st['errors'] = st['errors'][:10]
    return st


def rechecked(ev, st):
    """修正后的成功判据（rc 与 freed_gb 只作诊断，不作成功条件）。"""
    after = ev['after']
    zip_ok = (st['n_exact_zip'] == 1
              and all(x['r_exists'] for x in st['zip_records']))
    c = {
        'no_protected_in_targets': bool(ev['no_protected_in_targets']),
        'rc6_dir_gone': (not after['rc6_dir_exists']),
        'rc6_zip_gone': (not after['rc6_zip_exists']),
        'all_protected_present': all(after['protected'].values()),
        'recycle_dir_records_found': (st['n_under_rc6_dir'] > 0),
        'recycle_zip_record_found': (st['n_exact_zip'] == 1),
        'recycle_r_entities_present': (st['n_r_missing'] == 0 and zip_ok),
        'reversible': bool(st['n_under_rc6_dir'] > 0 and zip_ok
                           and st['n_r_missing'] == 0),
    }
    return c, all(c.values())


def main():
    ev = json.load(open(RAW, encoding='utf-8'))
    st = scan_recycle_bin()
    checks, ok = rechecked(ev, st)

    out = {
        'task': 'APP-099 第 0 节第 4 条：rc6 删除判据复核（不重跑删除）',
        'source': 'results/app/app438_app099_rc6_delete.json',
        'source_pass_field': 'pass',
        'source_pass_value': ev['pass'],
        'purpose': '修正 _app447 的成功判据；原始证据 write-once 不改写',
        'why_old_criterion_wrong': [
            'SHFileOperationW 返回值是 shell 专用码，rc=2 不等于「目标没删掉」；'
            '_app447 把 rc==0 当作唯一成功条件',
            'FOF_ALLOWUNDO 送回收站属同盘元数据移动 ⇒ C 盘可用空间不释放；'
            'freed_gb≈0 是正常结果，不能当失败',
            '真正需要证明的是：目标不在原位 + 保护对象完好 + 回收站可查（可逆）',
            '初版 $I 解析把 offset 24 当路径起点 ⇒ 只解出 1 个字符 ⇒ '
            '「回收站零命中」是假 FAIL；正确偏移为 28（offset 24 是路径字符数）',
        ],
        'recycle_bin_scan': st,
        'checks': checks,
        'pass_rechecked': bool(ok),
        'disk_space_note': {
            'before_free_gb': ev['before']['free_gb'],
            'after_free_gb': ev['after']['free_gb'],
            'freed_gb': ev['freed_gb'],
            'criterion': 'APP-099 只要求「删除前后各记一次 C 盘剩余空间」，'
                         '不要求释放空间；可逆删除（回收站）下 freed_gb≈0 属正常',
        },
        'shfileop_diagnostic': {
            'rc': ev['delete_result']['rc'],
            'aborted': ev['delete_result']['aborted'],
            'note': '只作诊断记录；rc=2 与「两个目标均已不在原位、且回收站两项可查」不矛盾',
        },
    }

    # ── 反证组：修正后的判据必须能被识破 ──
    neg = []

    def add(name, mutate, note):
        e = json.loads(json.dumps(ev))
        s = json.loads(json.dumps(st))
        mutate(e, s)
        _, good = rechecked(e, s)
        neg.append({'name': name, 'expect_pass': False,
                    'got_pass': bool(good), 'detected': (not good),
                    'note': note})

    add('dir_still_present',
        lambda e, s: e['after'].__setitem__('rc6_dir_exists', True),
        '目录没删掉 ⇒ 必须 FAIL')
    add('zip_still_present',
        lambda e, s: e['after'].__setitem__('rc6_zip_exists', True),
        'zip 没删掉 ⇒ 必须 FAIL')
    add('protected_missing',
        lambda e, s: e['after']['protected'].__setitem__(
            next(iter(e['after']['protected'])), False),
        'rc5/rc7 之一被动到 ⇒ 必须 FAIL')
    add('no_recycle_records',
        lambda e, s: (s.__setitem__('n_under_rc6_dir', 0),
                      s.__setitem__('n_exact_zip', 0),
                      s.__setitem__('zip_records', [])),
        '找不到回收站记录 ⇒ 无法证明可逆 ⇒ 必须 FAIL')
    add('recycle_r_entity_missing',
        lambda e, s: (s.__setitem__('n_r_missing', 1),
                      [x.__setitem__('r_exists', False)
                       for x in s['zip_records']]),
        '$R 实体不在 ⇒ 回收站记录残缺 ⇒ 必须 FAIL')

    out['negative_controls'] = neg
    out['n_neg'] = len(neg)
    out['n_neg_detected'] = sum(1 for x in neg if x['detected'])
    out['old_criterion_on_real_data'] = {
        'recomputed': bool(ev['no_protected_in_targets']
                           and not ev['after']['rc6_dir_exists']
                           and not ev['after']['rc6_zip_exists']
                           and all(ev['after']['protected'].values())
                           and ev['delete_result']['rc'] == 0),
        'note': '旧判据 rc==0 不成立 ⇒ 对真实数据误报 FAIL',
    }
    out['status_field_note'] = (
        'STATUS §175 请以本文件 pass_rechecked 与 disk_space_note 为准；'
        'app438 的 pass=false 是旧判据输出，作废但保留原始证据。')
    out['pass'] = bool(
        ok and out['n_neg_detected'] == out['n_neg']
        and out['old_criterion_on_real_data']['recomputed'] is False
        and st['n_under_rc6_dir'] > 0 and st['n_exact_zip'] == 1)

    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print('OUT=%s' % OUT)
    print('pass=%s pass_rechecked=%s n_i=%d dir=%d zip=%d r_missing=%d neg=%d/%d'
          % (out['pass'], out['pass_rechecked'], st['n_i_records_scanned'],
             st['n_under_rc6_dir'], st['n_exact_zip'], st['n_r_missing'],
             out['n_neg_detected'], out['n_neg']))
    for x in st['zip_records']:
        print('  ZIP_RB %-90s size=%s r_exists=%s when_local=%s'
              % (x['orig_path'][-90:], x['size_bytes'],
                 x['r_exists'], x['deleted_local_utc8']))
    for x in st['dir_samples']:
        print('  DIR_RB %-90s r_exists=%s when_local=%s'
              % (x['orig_path'][-90:], x['r_exists'], x['deleted_local_utc8']))
    for x in neg:
        print('  neg %-30s detected=%s' % (x['name'], x['detected']))
    return 0 if out['pass'] else 1


if __name__ == '__main__':
    raise SystemExit(main())

"""APP-148 §1a：**MT3 权重确认（不算 SHA）**。

要求（reviewer 原文）：
* 从**候选目录**和**源目录** `hy_bench\\ov\\mt3-int8sym-cw-q` 的 `openvino_model.bin`
  各读 **3 处固定偏移**的 **32 字节**（偏移 **4096**、**文件长度的一半**、**文件末尾前 4096**），
  逐处比较 hex；
* 同时对 **MT2 源目录** `mt2-int8sym-cw-q` 读同样 3 处，
  确认**和 MT3 一致、和 MT2 不一致**；
* MT3 和 MT2 架构、xml、字节数都相同，只看 config 和大小分不出来；
* **把 6 组 hex 写进 STATUS**。

🔴 口径：**不算 SHA**（APP-145：取消所有 SHA 校验与回报）⇒ 只用固定偏移的 32 字节 hex。
"""
import io, json, os, sys, time

HOME = r'C:\Users\Trekker-PTL'
CAND_MT3 = os.path.join(HOME, 'Confucius4_LiveCaption_MiniMVP_v1.2.candidate',
                         'models', 'mt', 'mt3-int8sym-cw-q')
SRC_MT3 = os.path.join(HOME, 'hy_bench', 'ov', 'mt3-int8sym-cw-q')
SRC_MT2 = os.path.join(HOME, 'hy_bench', 'ov', 'mt2-int8sym-cw-q')
OUT = r'C:\Users\Trekker-PTL\confucius4-openvino\results\app\app148_mt3_weight_check.json'

N = 32          # 读 32 字节
OFF1 = 4096     # 偏移 1
OFF3 = 4096     # 末尾前 4096


def offsets(size: int):
    """3 处固定偏移：4096 / 文件长度的一半 / 文件末尾前 4096。"""
    return [OFF1, size // 2, max(0, size - OFF3)]


def sample(path: str):
    size = os.path.getsize(path)
    with open(path, 'rb') as f:
        data = {}
        for i, off in enumerate(offsets(size), 1):
            f.seek(off)
            b = f.read(N)
            assert len(b) == N, '读不足 %d 字节 @ %s:%d' % (N, path, off)
            data['off%d' % i] = {'offset': off, 'hex': b.hex()}
    return size, data


def main():
    res = {'generated_at': time.strftime('%Y-%m-%d %H:%M:%S'),
           'method': 'fixed-offset 32-byte hex comparison (NO SHA)',
           'read_bytes': N, 'offsets_rule': ['4096', 'filesize//2', 'filesize-4096']}

    cand_bin = os.path.join(CAND_MT3, 'openvino_model.bin')
    src3_bin = os.path.join(SRC_MT3, 'openvino_model.bin')
    src2_bin = os.path.join(SRC_MT2, 'openvino_model.bin')
    for p in (cand_bin, src3_bin, src2_bin):
        assert os.path.isfile(p), '缺少文件：%s' % p

    c_size, c_data = sample(cand_bin)
    s3_size, s3_data = sample(src3_bin)
    s2_size, s2_data = sample(src2_bin)
    res['sizes'] = {'candidate_mt3': c_size, 'source_mt3': s3_size, 'source_mt2': s2_size}
    res['candidate_mt3'] = c_data
    res['source_mt3'] = s3_data
    res['source_mt2'] = s2_data

    # 判定
    cand_vs_src3 = {k: (c_data[k]['hex'] == s3_data[k]['hex'])
                    for k in ('off1', 'off2', 'off3')}
    mt3_vs_mt2 = {k: (s3_data[k]['hex'] == s2_data[k]['hex'])
                  for k in ('off1', 'off2', 'off3')}
    res['cand_mt3_vs_src_mt3'] = cand_vs_src3
    res['src_mt3_vs_src_mt2'] = mt3_vs_mt2

    res['verdict'] = {
        'candidate_mt3_matches_source_mt3': all(cand_vs_src3.values()),
        'mt3_differs_from_mt2_at_all_3_offsets': not any(mt3_vs_mt2.values()),
        'candidate_mt3_differs_from_mt2': (c_size != s2_size) or (
            not all(mt3_vs_mt2.values())),
        'same_size_mt3_vs_mt2': (s3_size == s2_size),
    }
    # 6 组 hex（写入 STATUS 用）
    res['six_hex_groups'] = {
        'candidate_mt3_off1': c_data['off1']['hex'],
        'candidate_mt3_off2': c_data['off2']['hex'],
        'candidate_mt3_off3': c_data['off3']['hex'],
        'source_mt3_off1': s3_data['off1']['hex'],
        'source_mt3_off2': s3_data['off2']['hex'],
        'source_mt3_off3': s3_data['off3']['hex'],
        'source_mt2_off1': s2_data['off1']['hex'],
        'source_mt2_off2': s2_data['off2']['hex'],
        'source_mt2_off3': s2_data['off3']['hex'],
    }

    print('文件大小：candidate_mt3=%d  source_mt3=%d  source_mt2=%d'
          % (c_size, s3_size, s2_size))
    print('\n6 组 hex（候选 mt3 / 源 mt3 / 源 mt2）：')
    for k, v in res['six_hex_groups'].items():
        print('  %-24s %s' % (k, v))
    print('\n候选 mt3 vs 源 mt3（逐偏移一致？）：%s' % res['cand_mt3_vs_src_mt3'])
    print('源 mt3 vs 源 mt2（逐偏移相同？）：%s' % res['src_mt3_vs_src_mt2'])
    print('\n判定：%s' % json.dumps(res['verdict'], ensure_ascii=False, indent=2))

    ok = (res['verdict']['candidate_mt3_matches_source_mt3']
          and res['verdict']['mt3_differs_from_mt2_at_all_3_offsets'])
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    io.open(OUT, 'w', encoding='utf-8', newline='\n').write(
        json.dumps(res, ensure_ascii=False, indent=2))
    print('\n落盘 ->', OUT)
    print('结论：%s' % ('PASS' if ok else 'FAIL'))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())

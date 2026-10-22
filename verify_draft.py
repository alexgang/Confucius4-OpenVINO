# -*- coding: utf-8 -*-
"""验证「草稿译文默认关闭 / 可运行时开关」的行为。"""
import os, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'live_caption'))

from translator import TranslationService, _Job

fails = []


def check(name, cond, extra=''):
    print(('PASS  ' if cond else 'FAIL  ') + name + ('   ' + str(extra) if extra else ''))
    if not cond:
        fails.append(name)


def mk(active=True):
    """造一个不启动线程的 TranslationService 实例。
    active 是只读 property（target != 'off'），所以用 target 控制。
    """
    svc = TranslationService(target='zh' if active else 'off', auto=False)
    svc.state = 'ready'          # 假装模型已就绪
    svc.draft = ''
    svc._draft_key = ''
    svc._draft_last = 0.0
    # 阻断实际入队后的翻译执行（线程没起，job 会堆在队列里，正好便于断言）
    return svc


# ① 默认关闭：maybe_draft 不入队
svc = mk()
check('默认 draft_on 为 False', svc.draft_on is False, 'draft_on=%r' % (svc.draft_on,))
svc.maybe_draft('今天天气不错')
check('默认关闭时 maybe_draft 不入队', svc.q.qsize() == 0, 'qsize=%d' % svc.q.qsize())

# ② 打开后入队
svc.set_draft(True)
svc.maybe_draft('今天天气不错')
check('打开后 maybe_draft 入队', svc.q.qsize() == 1, 'qsize=%d' % svc.q.qsize())
job = svc.q.get_nowait()
check('入队的是 draft 任务', job.kind == 'draft', 'kind=%r' % (job.kind,))

# ③ 关闭时清空残留草稿
svc.draft = '残留草稿'
svc._draft_key = 'xyz'
svc.set_draft(False)
check('关闭后清空残留 draft', svc.draft == '', 'draft=%r' % (svc.draft,))
check('关闭后清空 _draft_key', svc._draft_key == '', 'key=%r' % (svc._draft_key,))
svc.qsize = getattr(svc.q, 'qsize', None)
svc.q.put(_Job('draft', 'k1', 'x'))     # 塞一个任务再开再关
svc.set_draft(True)
svc.set_draft(False)
check('关闭后 draft_on 为 False', svc.draft_on is False)

# ④ 积压超阈值时即使打开也不入队（定稿翻译不受影响）
svc2 = mk()
svc2.set_draft(True)
svc2.maybe_draft('积压测试句', asr_backlog=0.9)   # 0.9 >= DRAFT_PAUSE_BACKLOG 0.5
check('积压 0.9s 时不入队', svc2.q.qsize() == 0, 'qsize=%d' % svc2.q.qsize())
svc2.maybe_draft('积压测试句', asr_backlog=0.1)   # 积压小 -> 应入队
check('积压 0.1s 时入队', svc2.q.qsize() == 1, 'qsize=%d' % svc2.q.qsize())

# ⑤ 定稿翻译链路不受 draft_on 影响（done 字典由 worker 写入，模拟写入）
svc3 = mk()
svc3.set_draft(False)
svc3.done['定稿句'] = 'final translation'
check('关闭草稿时定稿译文仍可取到', svc3.get('定稿句') == 'final translation')

# ⑥ 类上不再有 DRAFT_ON 常量（改为实例属性）
check('TranslationService 无 DRAFT_ON 类常量', not hasattr(TranslationService, 'DRAFT_ON'))
check('实例有 draft_on 属性', hasattr(mk(), 'draft_on'))

# ⑦ 构造参数 draft=True / draft=False
check('构造 draft=True -> True', TranslationService(target='zh', auto=False, draft=True).draft_on is True)
check('构造 draft=False -> False', TranslationService(target='zh', auto=False, draft=False).draft_on is False)
check('构造不传 draft -> False（默认关闭）', TranslationService(target='zh', auto=False).draft_on is False)

print()
print('=' * 56)
if fails:
    print('FAILED %d 项：%s' % (len(fails), fails))
    sys.exit(1)
print('ALL PASS')

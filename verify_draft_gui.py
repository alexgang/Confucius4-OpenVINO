# -*- coding: utf-8 -*-
"""验证 GUI 侧的草稿开关：初始值判定 + 复选框回调 + 渲染过滤（无 Tk 模拟）。"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'live_caption'))

import live_caption_app as A

fails = []


def check(name, cond, extra=''):
    print(('PASS  ' if cond else 'FAIL  ') + name + ('   ' + str(extra) if extra else ''))
    if not cond:
        fails.append(name)


class Args:
    def __init__(self, **kw):
        self.__dict__.update(kw)


# ① 初始值判定
os.environ.pop('LIVECAP_DRAFT', None)
check('无 --mt-draft 无 env -> 关闭', A._init_draft_flag(Args()) is False)
check('--mt-draft -> 开启', A._init_draft_flag(Args(mt_draft=True)) is True)
os.environ['LIVECAP_DRAFT'] = '1'
check('env=1 -> 开启', A._init_draft_flag(Args()) is True)
check('--mt-draft=False 但 env=1 -> 仍开启(env 为脚本入口)', A._init_draft_flag(Args(mt_draft=False)) is True)
os.environ.pop('LIVECAP_DRAFT', None)
check('无 --mt-draft 无 env -> 关闭(再确认)', A._init_draft_flag(Args()) is False)


# ② 复选框回调（无 Tk 模拟）
class FakeVar:
    def __init__(self, v):
        self.v = v

    def get(self):
        return self.v

    def set(self, v):
        self.v = v


class FakeMT:
    def __init__(self):
        self.draft_on = False
        self.draft = 'x'
        self.active = True
        self.calls = []

    def set_draft(self, on):
        self.draft_on = bool(on)
        self.calls.append(bool(on))
        if not self.draft_on:
            self.draft = ''
        return self.draft_on


class FakeApp:
    _on_mt_draft_toggled = A.App._on_mt_draft_toggled

    def __init__(self):
        self.mt = FakeMT()
        self.var_mt_draft = FakeVar(False)
        self.var_status = FakeVar('')
        self.logs = []
        self._ui_log = self.logs.append


app = FakeApp()
app.var_mt_draft.set(True)
app._on_mt_draft_toggled()
check('勾选后 draft_on=True', app.mt.draft_on is True)
check('勾选后状态栏有提示', '草稿译文已开启' in app.var_status.get(), app.var_status.get())
check('勾选后写了日志', any('开启' in m for m in app.logs), app.logs)

app.var_mt_draft.set(False)
app._on_mt_draft_toggled()
check('取消后 draft_on=False', app.mt.draft_on is False)
check('取消后状态栏有提示', '草稿译文已关闭' in app.var_status.get(), app.var_status.get())
check('取消后残留草稿被清掉', app.mt.draft == '', repr(app.mt.draft))


# ③ 渲染过滤逻辑（复刻 _render 里的条件）
def render_draft(mt):
    return mt.draft if (mt.active and mt.draft_on) else ''


mt = FakeMT()
mt.draft = '预览译文'
check('渲染：草稿关闭时不显示', render_draft(mt) == '')
mt.draft_on = True
check('渲染：草稿打开时显示', render_draft(mt) == '预览译文')
mt.active = False
check('渲染：翻译未激活时不显示', render_draft(mt) == '')

print()
print('=' * 56)
if fails:
    print('FAILED %d 项：%s' % (len(fails), fails))
    sys.exit(1)
print('ALL PASS')

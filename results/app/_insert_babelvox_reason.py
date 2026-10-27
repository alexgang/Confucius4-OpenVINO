# -*- coding: utf-8 -*-
"""一次性工具：往 live_caption/tts_worker.py 顶层插入 `_babelvox_failure_reason()`。

🔴 纪律：仓库 live_caption/ 与客户包 app/ 是两份独立副本 ⇒ 定点插入，
   用「唯一命中断言」保证只插一次（幂等）。
"""
import io
import os
import sys

TARGET = sys.argv[1]

FUNC = '''

# ── APP-023③：把「BabelVox 加载失败」翻译成人话 ──────────────────────────
def _babelvox_import_error() -> str:
    """探测 babelvox（Qwen3-TTS 运行时）是否可导入。返回错误串，'' 表示可用。

    🔴 为什么单独探测：异常链里 `e` 可能是**任何**环节
      （缺运行时 / 模型编译失败 / 设备不支持）⇒ 界面必须能区分。
    """
    try:
        import babelvox  # noqa: F401
        return ''
    except Exception as e:
        return '%s: %s' % (type(e).__name__, e)


def _babelvox_failure_reason(e, device='', precision='') -> str:
    """把 BabelVox 加载失败翻译成**一句用户能看懂、能处理**的话。

    🔴🔴 APP-023③ / APP-025：旧实现只在日志里写「BabelVox 引擎不可用 ⇒
       回落旧引擎」，而界面最终显示的是 `rc=3221226505`（进程级 abort）
       ⇒ **用户完全无从下手**（这正是用户 09:06 反馈的原话）。

    两种情形必须分开说：
      ① **缺运行时**（`import babelvox` 都不行）⇒ 明确报「缺少 Qwen3-TTS
         运行时（babelvox）」+ 指引（要用随包的 python）；
      ② **运行时在、但引擎起不来**（模型/设备/编译）⇒ 报「Qwen3-TTS 引擎
         加载失败」+ 原始异常，并说明**不会**回落旧引擎。
    """
    miss = _babelvox_import_error()
    if miss:
        return ('缺少 Qwen3-TTS 运行时（babelvox）：%s。'
                '请用随客户包分发的 python（<包根>\\\\python\\\\python.exe）启动，'
                '该运行时随包提供、无需联网安装。' % miss)
    where = ''
    if device or precision:
        where = '（设备 %s / 精度 %s）' % (device or '-', precision or '-')
    return ('Qwen3-TTS 引擎加载失败%s：%s。'
            '已不再回落旧的 Confucius4-TTS 引擎 —— 它的动态形状 IR 在 '
            'NPU/GPU 上必然编译失败并导致进程崩溃。' % (where, e))

'''

ANCHOR = 'def resolve_out_device(device):'


def main():
    src = io.open(TARGET, encoding='utf-8').read()
    # 🔴 判据必须是「**定义**存在」，不能只看名字 —— 调用处（`raise RuntimeError(
    #   _babelvox_failure_reason(...))`）也会命中名字 ⇒ 会被误判成已插入
    #   ⇒ 函数永远插不进去（本轮实际踩到）。
    if 'def _babelvox_failure_reason' in src:
        print('SKIP: 已定义（幂等）')
        return 0
    n = src.count(ANCHOR)
    if n != 1:
        print('FAIL: 锚点命中 %d 次（要求恰好 1 次）' % n)
        return 1
    out = src.replace(ANCHOR, FUNC.lstrip('\n') + '\n' + ANCHOR, 1)
    io.open(TARGET, 'w', encoding='utf-8', newline='\n').write(out)
    print('OK: 已插入，文件 %s' % TARGET)
    return 0


if __name__ == '__main__':
    sys.exit(main())

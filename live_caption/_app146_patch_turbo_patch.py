"""给**客户包内**的 `app/tts_engine_patch.py` 加 NPU turbo 注入（APP-139）。

## 为什么必须改这个文件（实测定位到的真正编译点）

APP-146 第 2 项要求「每个 NPU 模型的 `NPU_TURBO` 实际值都已打印」。
实测（三轮 e2e 的 bridge.log）**日志里根本没有 turbo 行** ⇒ 查下来：

* EXT 的 TTS 走 App 的 `tts_engine.make_engine` ⇒ 走 `MultiDecoderBabelVox`
  ⇒ 真正的 NPU 编译在 **`babelvox/pipeline.py::_compile_npu`**：
      `return core.compile_model(model, "NPU"), "NPU"`   ← **不传任何属性**
  ⇒ turbo **无处可注入**（`NPU_TURBO` 只在 `compile_model` 的**第三参数**里才生效）；
* App 的 `tts_engine.py` 里我加的两处（cp_prefill / cp_decode 迁移）是**另一条路径**
  ⇒ 实测中根本没被触发。

## 修法

**覆写** `tts_engine_patch.py` 里 `MultiDecoderBabelVox._compile_npu`：
自己带 turbo 属性编译（用 `npu_turbo.turbo_props`）⇒ 成功就用它；
**失败（属性不被支持等）就退回 `super()._compile_npu`**（保持原有行为，不让 turbo 拖垮 TTS）。

🔴 纪律：定点替换 + 唯一命中断言；写前备份；写后 ast.parse + 逐字节复核。
🔴 只改**客户包内**的 vendored 副本（`app/tts_engine_patch.py`）——
   **不改** TTS 模块的 `qwen3tts_eval/qwen3tts_patch.py`（那是 TTS 模块的文件）。
"""
import ast
import io
import os
import shutil
import sys

CAND = r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_MiniMVP_v1.2.candidate'
P = os.path.join(CAND, 'app', 'tts_engine_patch.py')
TAG = 'app146_turbo_patch'


def main():
    src = io.open(P, encoding='utf-8', newline='').read()
    NL = '\r\n' if '\r\n' in src else '\n'

    # ── 定位 `_compile_npu` 的覆写点（单行锚点）──────────────────────
    anchor = "    def _compile_npu(self, core, model, name):"
    assert src.count(anchor) == 1, '锚点命中 %d 次' % src.count(anchor)

    old_body = NL.join([
        "    def _compile_npu(self, core, model, name):",
        "        if (name == 'tokenizer_decoder' and self.decoder_buckets",
        "                and os.environ.get('LIVECAP_TTS_EAGER_DEC512') != '1'):",
        "            return _LazyCompiled(core, model, super()._compile_npu, name), 'NPU'",
        "        return super()._compile_npu(core, model, name)",
    ])
    assert src.count(old_body) == 1, '函数体命中 %d 次' % src.count(old_body)

    new_body = NL.join([
        "    def _compile_npu(self, core, model, name):",
        "        if (name == 'tokenizer_decoder' and self.decoder_buckets",
        "                and os.environ.get('LIVECAP_TTS_EAGER_DEC512') != '1'):",
        "            return _LazyCompiled(core, model, super()._compile_npu, name), 'NPU'",
        "        # 🔴🔴🔳 **APP-139（2026-11-26）：NPU turbo 注入点**",
        "        #",
        "        # ★ 为什么必须在这里注入（实测定位）：",
        "        #   真正的 NPU 编译在 `babelvox/pipeline.py::_compile_npu`：",
        "        #       `return core.compile_model(model, \"NPU\"), \"NPU\"`",
        "        #   ⇒ **不传任何属性** ⇒ turbo 无处可注入",
        "        #   （`NPU_TURBO` 只在 `compile_model` 的**第三参数（编译期 config）**里生效；",
        "        #     `set_property` 会被 CPU/AUTO 插件拒 —— TTS 模块 2026-11-02 实测）。",
        "        #",
        "        # ★ 口径：**默认开**；设备/驱动不支持 ⇒ **退回不带 turbo**；",
        "        #   编译失败 ⇒ 退回 `super()._compile_npu`（保持原行为，**不让 turbo 拖垮 TTS**）。",
        "        # ★ 日志打**实际值**（APP-139 的验收项）。",
        "        try:",
        "            from npu_turbo import turbo_props as _turbo_props",
        "        except Exception:",
        "            _turbo_props = None",
        "        if _turbo_props is not None:",
        "            try:",
        "                props = _turbo_props(core=core, on_log=_turbo_log)",
        "                if props:",
        "                    cm = core.compile_model(model, \"NPU\", props)",
        "                    _turbo_log('[tts_engine_patch] NPU turbo 已生效：%s（%s）'",
        "                               % (props.get('NPU_TURBO'), name))",
        "                    return cm, \"NPU\"",
        "            except Exception as e:",
        "                _turbo_log('[tts_engine_patch] NPU turbo 编译失败（%s: %s）"
        "⇒ 退回原路径（不带 turbo）'",
        "                           % (type(e).__name__, e))",
        "        return super()._compile_npu(core, model, name)",
    ])

    new = src.replace(old_body, new_body, 1)

    # ── 加一个模块级日志函数（放在文件顶部的 import 之后）─────────────
    log_anchor = "logger = logging.getLogger(__name__)"
    if src.count(log_anchor) == 1:
        helper = NL.join([
            "",
            "",
            "def _turbo_log(msg):",
            "    \"\"\"APP-139：turbo 的日志（走 babelvox 的 logger ⇒ 落进 bridge.log）。\"\"\"",
            "    try:",
            "        logger.info(msg)",
            "    except Exception:",
            "        pass",
        ])
        new = new.replace(log_anchor, log_anchor + helper, 1)
    else:
        # 没有 logger 锚点 ⇒ 追加到文件末尾
        helper = NL.join([
            "",
            "",
            "def _turbo_log(msg):",
            "    \"\"\"APP-139：turbo 的日志。\"\"\"",
            "    try:",
            "        print(msg, flush=True)",
            "    except Exception:",
            "        pass",
        ])
        new = new + helper

    # ── 不变量 ───────────────────────────────────────────────────────
    ast.parse(new)
    assert new.count('_turbo_props(core=core') == 1, '注入点应恰好 1 处'
    assert new.count('def _turbo_log') == 1
    # 行尾：**风格不变**（仍是纯 CRLF/纯 LF），且裸 LF 数不变
    def _bare(b):
        return b.count(b'\n') - b.count(b'\r\n')
    _nb, _ob = new.encode('utf-8'), src.encode('utf-8')
    assert _bare(_nb) == _bare(_ob), '混入裸 LF：%d -> %d' % (_bare(_ob), _bare(_nb))
    if NL == '\r\n':
        assert _nb.count(b'\r\n') - _ob.count(b'\r\n') == _nb.count(b'\n') - _ob.count(b'\n'), \
            'CRLF 增量与行数增量不符'
    else:
        assert _nb.count(b'\r\n') == _ob.count(b'\r\n'), 'LF 文件里出现了 CRLF'

    bak = P + '.bak_' + TAG
    if not os.path.exists(bak):
        shutil.copy2(P, bak)
    tmp = P + '.tmp_' + TAG
    io.open(tmp, 'w', encoding='utf-8', newline='').write(new)
    os.replace(tmp, P)
    assert io.open(P, encoding='utf-8', newline='').read() == new, '写后逐字节复核失败'
    print('WRITTEN', P)
    print('bytes %d -> %d' % (len(src.encode('utf-8')), len(new.encode('utf-8'))))


if __name__ == '__main__':
    sys.exit(main())

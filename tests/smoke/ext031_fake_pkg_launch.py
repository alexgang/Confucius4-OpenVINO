# -*- coding: utf-8 -*-
"""ext031_fake_pkg_launch.py — ★★ EXT-031② 的**可执行证据**：
证明发行包里的桥接**不依赖任何开发机目录**。

## 做法（**不是**看代码，是真跑）

1. 造一个**模拟发行包根** `PKGROOT`（目录名故意**不叫** `live_dub_ext`）：
   ```
   PKGROOT/
     app/            ← 放 App 的 app/ 关键文件（seg_stream.py / translator.py / tts_engine.py …）
     models/…        ← 符号链接或空目录占位（模型**不另带一份**）
     ext/            ← 本插件代码（**整个目录拷进来**，模拟打进包）
     python/         ← 不放 python.exe（用 App 自带解释器的绝对路径跑）
   ```
2. **把开发机目录从视野里彻底切掉**：
   - `EXT_APP_ROOT` 指向模拟包里的 `app/` 所在目录；
   - `EXT_APP_SEARCH_ROOT` 指向一个**空目录**（⇒ 不许回退到开发机的
     `Confucius4_LiveCaption_v*`）；
   - 环境里**清掉** `EXT_R2T2_ROOT` / `EXT_HY_ROOT` / `EXT_TTS_ROOT`
     / `EXT_SPK_SEG_IR` / `EXT_SPK_WES_IR`（不许显式覆盖）。
3. 在模拟包根里**真启动**桥接（回声模式 ⇒ 不占 GPU/NPU、不跑推理），
   打印 `stats()` 里与路径有关的字段。
4. 判定：
   - 引擎探测根 / 模型目录**全部落在模拟包内**（含 `PKGROOT` 字符串）
     ⇒ ✅ 不依赖开发目录；
   - 任何一处仍指向 `live_dub_ext` / `hy_bench` / `confucius4-openvino`
     / `Worktrees` ⇒ ❌ **FAIL**。

## 运行
    python tests/smoke/ext031_fake_pkg_launch.py
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PY = sys.executable

# ★ 发行包里**禁止**出现的开发机路径片段
FORBIDDEN = ("live_dub_ext", "hy_bench", "confucius4-openvino",
             "qwen3tts_eval", "Worktrees", "confucius4-tts")

RESULTS = []


def check(name: str, cond: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(cond), detail))
    print("  [%s] %s%s" % ("PASS" if cond else "FAIL", name,
                           (" — " + detail) if detail else ""))


def _fake_app_files(app_dir: str) -> None:
    """在模拟包的 app/ 里放**探测用的关键文件**。

    ★ 只放**探测逻辑真正检查的那几个符号**，不复制整个 App
      （本脚本验证的是**路径解析**，不是引擎推理）。
    """
    os.makedirs(app_dir, exist_ok=True)
    # ASR 探测需要 `SegmentedStreamer`（engines._probe 的 needle）
    with open(os.path.join(app_dir, "seg_stream.py"), "w", encoding="utf-8") as f:
        f.write("# fake seg_stream for EXT-031 path probe\n"
                "class SegmentedStreamer:\n    pass\n")
    # MT 探测需要 `mt_available`
    with open(os.path.join(app_dir, "translator.py"), "w", encoding="utf-8") as f:
        f.write("# fake translator for EXT-031 path probe\n"
                "def mt_available():\n    return True\n")
    # TTS 探测需要 `tts`
    with open(os.path.join(app_dir, "tts_engine.py"), "w", encoding="utf-8") as f:
        f.write("# fake tts_engine for EXT-031 path probe\n"
                "def tts(*a, **k):\n    return b''\n")
    # 说话人 runtime + 模型占位
    spk = os.path.join(app_dir, "asr_spk")
    os.makedirs(spk, exist_ok=True)
    with open(os.path.join(spk, "asr052_spk_runtime.py"), "w", encoding="utf-8") as f:
        f.write("# fake asr052_spk_runtime\n")
    for rel in (("models", "encoder-int8"), ("models", "decoder-gpu-int8"),
                ("models", "mt", "mt2-int8sym-cw-q"), ("models", "qwen3tts"),
                ("models", "spk", "pyannote_seg_3_0", "fp16"),
                ("models", "spk", "wespeaker-resnet34-fp16")):
        os.makedirs(os.path.join(os.path.dirname(app_dir), *rel), exist_ok=True)


PROBE = r'''
import json, os, sys
sys.path.insert(0, os.path.join(PKG, "ext_parent"))
from ext import engines, segmenter
from ext.app_root import resolve_app_root, package_root
from ext.speaker_bypass import SpeakerBypass
from ext import config as C

avail = engines.EngineAdapter().available()
sb = SpeakerBypass(device_lock=None)
seg_ir, wes_ir = sb._asset_paths()

out = {
    "pkg": PKG,
    "app_root": resolve_app_root(),
    "package_root": package_root(),
    "engines": avail,
    "model_dirs": engines.ENGINE_MODEL_DIRS,
    "r2t2_root": segmenter.R2T2_ROOT,
    "seg_ir": seg_ir,
    "wes_ir": wes_ir,
    "release_mode": C.RELEASE_MODE,
    "capture_modes": C.CAPTURE_MODES,
}
print("@@JSON@@" + json.dumps(out, ensure_ascii=False))
'''


def main() -> int:
    print("=" * 68)
    print("EXT-031② 自测：不依赖开发目录（模拟发行包根启动）")
    print("=" * 68)

    tmp = tempfile.mkdtemp(prefix="ext031_pkg_")
    try:
        # ── 造模拟发行包根（目录名**故意不叫** live_dub_ext）──
        pkg = os.path.join(tmp, "Confucius4_LiveCaption_v2.0")
        os.makedirs(pkg)
        app_dir = os.path.join(pkg, "app")
        _fake_app_files(app_dir)
        # 本插件代码：**整个 ext/ 拷进去**（模拟打进包）
        shutil.copytree(os.path.join(ROOT, "ext"), os.path.join(pkg, "ext"),
                        ignore=shutil.ignore_patterns("__pycache__"))
        # ext/ 的父目录（package_root() 会算成 pkg）
        pkg_parent = pkg

        print("模拟包根：%s" % pkg)

        # ── 跑探针：EXT_APP_ROOT 指向模拟包 ⇒ 绝不许回退到开发机 ──
        empty_search = os.path.join(tmp, "empty_search")
        os.makedirs(empty_search, exist_ok=True)

        env = dict(os.environ)
        for k in ("EXT_R2T2_ROOT", "EXT_HY_ROOT", "EXT_TTS_ROOT",
                  "EXT_SPK_SEG_IR", "EXT_SPK_WES_IR", "EXT_APP_SEARCH_ROOT"):
            env.pop(k, None)
        env["EXT_APP_ROOT"] = pkg
        env["EXT_APP_SEARCH_ROOT"] = empty_search
        env["PYTHONPATH"] = pkg_parent

        probe_src = ("PKG = %r\nEXT_PARENT = %r\n" % (pkg, pkg_parent)) + PROBE
        probe_py = os.path.join(tmp, "probe.py")
        with open(probe_py, "w", encoding="utf-8") as f:
            f.write(probe_src)

        proc = subprocess.run([PY, probe_py], env=env, cwd=tmp,
                              capture_output=True, text=True, encoding="utf-8")
        blob = proc.stdout or ""
        m = re.search(r"@@JSON@@(\{.*\})", blob, re.S)
        check("探针进程正常退出（rc=0）", proc.returncode == 0,
              (proc.stderr or "")[-400:])
        if not m:
            check("探针输出含 @@JSON@@", False, blob[-400:] + (proc.stderr or "")[-400:])
            return 1
        data = json.loads(m.group(1))

        # ── 判定 1：App 根 = 模拟包 ──
        check("resolve_app_root() 指向**模拟包**（不是开发机）",
              os.path.normcase(str(data.get("app_root") or ""))
              == os.path.normcase(pkg),
              "app_root=%r" % data.get("app_root"))

        # ── 判定 2：三个引擎根 + 模型目录全部在模拟包内 ──
        eng = data.get("engines") or {}
        paths = []
        for k in ("asr", "mt", "tts"):
            paths.append(eng.get(k, {}).get("root") or "")
            paths.extend(eng.get(k, {}).get("model_dirs") or [])
        paths.append(data.get("r2t2_root") or "")
        paths.append(data.get("seg_ir") or "")
        paths.append(data.get("wes_ir") or "")
        outside = [p for p in paths
                   if p and os.path.normcase(pkg) not in os.path.normcase(p)]
        check("引擎根 / 模型目录 / 说话人 IR **全部落在模拟包内**",
              not outside,
              "越界项：%r" % (outside or "无"))

        # ── 判定 3：不含任何开发机目录名 ──
        blob_all = json.dumps(data, ensure_ascii=False)
        hits = [w for w in FORBIDDEN if w in blob_all]
        check("解析结果里**不含**任何开发机目录名", not hits,
              "命中：%r" % (hits or "无"))

        # ── 判定 4：package_root() = 模拟包（相对包根）──
        check("package_root() = 模拟包根（相对包根解析）",
              os.path.normcase(str(data.get("package_root") or ""))
              == os.path.normcase(pkg),
              "package_root=%r" % data.get("package_root"))

        # ── 判定 5：发行版模式下只保留 tabCapture ──
        env2 = dict(env)
        env2["EXT_RELEASE"] = "1"
        proc2 = subprocess.run([PY, probe_py], env=env2, cwd=tmp,
                               capture_output=True, text=True, encoding="utf-8")
        m2 = re.search(r"@@JSON@@(\{.*\})", proc2.stdout or "", re.S)
        if m2:
            d2 = json.loads(m2.group(1))
            check("EXT_RELEASE=1 ⇒ 抓流白名单只留 tabCapture（EXT-031③）",
                  d2.get("capture_modes") == ["tabCapture"]
                  and d2.get("release_mode") is True,
                  "release_mode=%r capture_modes=%r"
                  % (d2.get("release_mode"), d2.get("capture_modes")))
        else:
            check("EXT_RELEASE=1 探针可运行", False,
                  (proc2.stderr or "")[-300:])

        # ── 落盘证据 ──
        out_dir = os.path.join(ROOT, ".tmp", "ext031")
        os.makedirs(out_dir, exist_ok=True)
        out_json = os.path.join(out_dir, "fake_pkg_probe.json")
        with open(out_json, "w", encoding="utf-8") as f:
            json.dump({"pkg": pkg, "probe": data}, f,
                      ensure_ascii=False, indent=2)
        print("\n证据落盘：%s（%d B）" % (out_json, os.path.getsize(out_json)))

    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    npass = sum(1 for _n, ok, _d in RESULTS if ok)
    nfail = len(RESULTS) - npass
    print("=" * 68)
    print("结果：%d PASS / %d FAIL" % (npass, nfail))
    print("=" * 68)
    return 1 if nfail else 0


if __name__ == "__main__":
    sys.exit(main())

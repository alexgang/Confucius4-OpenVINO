# -*- coding: utf-8 -*-
"""§150 patrol: no new reviewer corrections (last_ack=APP-081 == max id 81).

定点写入 STATUS_APP.md：只改头部 3 行、整块归档 §149 正文并留速查、末尾追加 §150。
写前自检（反向还原 == 旧全文 / 章节不减 / LF 未破 / 限额 / 唯一命中）＋原子替换＋写后逐字节复核。
"""
import os
import re
import json
import hashlib
import ctypes
import subprocess
import datetime

ROOT = r"C:\Users\Trekker-PTL\confucius4-openvino"
CORR = ROOT + r"\status\app\CORRECTIONS_APP.md"
STAT = ROOT + r"\status\app\STATUS_APP.md"
ARCH = ROOT + r"\status\archive\STATUS_APP_sec149_20261107.md"
PJSON = ROOT + r"\results\app\app341_app_patrol_20261107.json"
LOCK = r"C:\Users\Trekker-PTL\shared\MACHINE_LOCK"

# 开工基线（本轮 17:35 实测，reviewer 独占文件）
OPEN_FP = {
    "sha256": "d80ad25d1da40a2714958cbf3c8491ebaf186edafa2aeec3b860607f47c5dd9a",
    "bytes": 227215,
    "mtime": "2026-11-07 14:51:02",
    "n_app_sections": 81,
    "max_app_id": 81,
}


def sh(b):
    return hashlib.sha256(b).hexdigest()


def corr_fp():
    b = open(CORR, "rb").read()
    return {
        "sha256": sh(b),
        "bytes": len(b),
        "mtime": datetime.datetime.fromtimestamp(os.stat(CORR).st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
        "n_app_sections": len(re.findall(rb"(?m)^## APP-\d+", b)),
        "max_app_id": max(int(x) for x in re.findall(rb"APP-(\d+)", b)),
    }


def run(cmd):
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return r.returncode, r.stdout.strip(), r.stderr.strip()


def now_ps():
    rc, out, err = run(["powershell.exe", "-NoProfile", "-Command",
                        "Get-Date -Format 'yyyy-MM-dd HH:mm:ss'"])
    assert rc == 0 and re.match(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$", out), (rc, out, err)
    return out


def pid_state(pid):
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    h = k32.OpenProcess(0x1000, False, pid)
    if not h:
        err = ctypes.get_last_error()
        return {"pid": pid, "verdict": "DEAD_err87" if err == 87 else "UNKNOWN_TREAT_AS_ALIVE", "err": err}
    code = ctypes.c_ulong()
    k32.GetExitCodeProcess(h, ctypes.byref(code))
    k32.CloseHandle(h)
    return {"pid": pid, "verdict": "ALIVE" if code.value == 259 else "DEAD_code_%d" % code.value, "err": 0}


def meta(path):
    b = open(path, "rb").read()
    return {
        "path": os.path.relpath(path, ROOT).replace("\\", "/"),
        "n_files": 1,
        "bytes": len(b),
        "mtime": datetime.datetime.fromtimestamp(os.stat(path).st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
        "sha256": sh(b),
    }


def main():
    checks = []

    def ck(name, cond, detail=""):
        checks.append({"name": name, "pass": bool(cond), "detail": str(detail)})
        assert cond, "CHECK FAILED: %s %s" % (name, detail)

    # ---------- A. 采集 ----------
    now = now_ps()
    close_fp = corr_fp()
    ck("corrections_open_equals_close", all(close_fp[k] == OPEN_FP[k] for k in OPEN_FP),
       "open=%s close=%s" % (OPEN_FP, close_fp))

    head = run(["git", "rev-parse", "--short", "HEAD"])[1]
    branch = run(["git", "rev-parse", "--abbrev-ref", "HEAD"])[1]
    ahead = int(run(["git", "rev-list", "--count", "origin/main..HEAD"])[1])
    st_lines = [x for x in run(["git", "status", "--short"])[1].splitlines() if x]
    corr_dirty = any("status/app/CORRECTIONS_APP.md" in x for x in st_lines)
    ck("git_head_is_4f0e931", head == "4f0e931", head)
    ck("git_branch_main", branch == "main", branch)
    ck("git_ahead_zero", ahead == 0, ahead)
    ck("corrections_not_staged_for_commit_rule", corr_dirty, "worktree modified; never add")

    lock_exists = os.path.exists(LOCK)
    pids = [pid_state(17220), pid_state(7396)]
    ck("machine_lock_absent", not lock_exists, lock_exists)
    ck("prior_pids_all_dead", all(p["verdict"] == "DEAD_err87" for p in pids), pids)

    # ---------- B. STATUS 原文 / §149 整块归档 ----------
    old_b = open(STAT, "rb").read()
    old = old_b.decode("utf-8")
    ck("old_status_lf_only", b"\r\n" not in old_b, old_b.count(b"\r\n"))
    ck("old_status_size", len(old_b) == 38768 and old_b.count(b"\n") + 1 == 183,
       "%d B / %d L" % (len(old_b), old_b.count(b"\n") + 1))

    m = re.search(r"(?m)^## §149[^\n]*$", old)
    ck("sec149_heading_unique", m is not None and len(re.findall(r"(?m)^## §149", old)) == 1)
    sec149 = old[m.start():]
    ck("sec149_is_last_section", old.count(sec149) == 1 and sec149.startswith("## §149"), len(sec149))
    arch_b = sec149.encode("utf-8")
    with open(ARCH, "wb") as f:
        f.write(arch_b)                       # 逐字整块，不加任何包装
    arch_meta = meta(ARCH)
    ck("archive_verbatim", open(ARCH, "rb").read() == arch_b, arch_meta["sha256"])

    sec141 = old[old.find("## §141"):old.find("## §142")]
    sec142 = old[old.find("## §142"):m.start()]
    ck("sec141_sec142_nonempty", len(sec141) > 100 and len(sec142) > 100)

    # ---------- C. 巡检事实 JSON（先落盘，供 §150 引用原始字段） ----------
    patrol = {
        "section": "§150",
        "patrol_time_get_date": now,
        "lease": {"module": "app", "token": "b68c0cf5", "acquire_exit": 0, "takeover": False},
        "corrections_file": {"path": "status/app/CORRECTIONS_APP.md",
                             "policy": "reviewer_exclusive__readonly_never_modified_never_committed"},
        "open_fingerprint": OPEN_FP,
        "close_fingerprint": close_fp,
        "last_ack": "APP-081",
        "n_app_sections": close_fp["n_app_sections"],
        "max_app_id": close_fp["max_app_id"],
        "new_items_after_last_ack": [],
        "verdict": "NO_NEW_CORRECTION__STOP_AT_REVIEWER_GATE",
        "stop_reason": [
            "APP-081 第 5 点：reviewer 自算 zip SHA / 抽查 zip 内容 / 看截图后才通知用户",
            "APP-081 第 6 点：不要再新增覆盖审计/静态自证类轮次；本条处理完前不自创其他任务",
            "任务规则：明确写了需要停下来等 reviewer 复核时，做到该节点即停止",
        ],
        "git": {"head": head, "branch": branch, "ahead": ahead,
                "n_worktree_changes": len(st_lines),
                "corrections_file_modified_in_worktree": corr_dirty,
                "policy": "per_file_git_add__no_-A__never_commit_CORRECTIONS_APP.md__ordinary_push_main"},
        "machine_lock": {"path": LOCK.replace("\\", "/"), "exists": lock_exists},
        "prior_background_pids": pids,
        "prior_evidence_fields": {
            "results/app/app339_v23_verify_final.json": "items(zip_sha/unzip_check/gui/cli=PASS, blacklist=UNKNOWN) / artifacts=20",
            "results/app/app332_v23_zip_sha.json": "sha256=4b4a977ab1dba640748e1a7347220089a384a7f7e9e8e6778b61902cbadcbfed / bytes=11235945990 / n_zip_entries=14320",
            "results/app/app337_v23_cli_rerun.json": "verdict=PASS / tts_final_stats.submitted=70 / zero_segment_check.n_bad_rows=0",
        },
        "archive_artifact": arch_meta,
        "discipline": {"packed": False, "new_zip": False, "pkg_dirs_modified": False,
                       "shortcut_modified": False, "user_notified": False,
                       "device_occupied": False, "cpu_inference_or_benchmark": False,
                       "minimax_called": False, "force_push": False,
                       "old_versions_untouched": "v2.0/v2.1/v2.2/v2.3"},
        "checks": checks,
    }
    pj_b = (json.dumps(patrol, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    with open(PJSON, "wb") as f:
        f.write(pj_b)
    pj_meta = meta(PJSON)
    ck("patrol_json_on_disk", open(PJSON, "rb").read() == pj_b, pj_meta["sha256"])

    # ---------- D. 构造 §150 + 头部定点替换 ----------
    quick = (
        "## §149 执行 APP-081（last_ack=APP-081）｜v2.3 新目录＋新 zip 已打，APP-080 ⑥ 全套验收（2026-11-07 17:14）\n\n"
        "> 🔴 **本节正文已整块逐字归档** ⇒ `status/archive/STATUS_APP_sec149_20261107.md`（"
        + str(arch_meta["bytes"]) + " B／块 SHA256 `" + arch_meta["sha256"] +
        "`；含开工/收尾指纹、4a–4e 全部原始字段、20 项产物清单、r1 事故与 reviewer 待裁定项）。\n"
        "> 🔴 **速查**：APP-081 **第 1–4 点已完成**（v2.3 新目录／新 zip `4b4a977a…cbfed`／14 320 条目／全套验收结果文件落盘）；"
        "**第 5 点需等 reviewer 复核**（自算 zip SHA／抽查 zip 内容／看 100%+150% 截图／裁定黑名单 1 项口径歧义与 `spk_conf` 缺陷）"
        "⇒ 复核通过后才由 reviewer 通知用户。\n"
    )

    sec150 = (
        "## §150 巡检无新纠偏（last_ack=APP-081）｜APP-081 第 5 点仍停在「需等 reviewer 复核」节点（" + now + "）\n\n"
        "- **步骤 1–3**：`status/app/CORRECTIONS_APP.md`（reviewer 独占，全程只读／未改／未提交）全文 **81 条**"
        "（APP-001..APP-081 无缺号），全文最大编号 **81**；`STATUS_APP.md` 头部 `last_ack: APP-081` ⇒ "
        "**编号大于 last_ack 的新条目 = 0**（`results/app/app341_app_patrol_20261107.json` → `new_items_after_last_ack=[]`、"
        "`verdict=NO_NEW_CORRECTION__STOP_AT_REVIEWER_GATE`），本轮无条目可执行。租约 `acquire app` exit 0"
        "（TOKEN `b68c0cf5`，**无 TAKEOVER**）。\n"
        "- 🔴 **本条需等 reviewer 复核**：APP-081 第 5 点明文「reviewer 将自算 SHA、抽查 zip 内容、看截图后再通知用户」；"
        "§149 已把 v2.3 全套验收原始结果文件与 20 项产物清单（逐项 `bytes`／`mtime`／`sha256`）落盘。按任务"
        "「若纠偏明确写了需要停下来等 reviewer 复核就做到那一步停止」＋ APP-081 第 6 点"
        "「不要再新增『覆盖审计/静态自证』类轮次、本条处理完前不自创其他任务」⇒ **本轮不自行推进、不自创任务、不重跑静态自证**。"
        "当前节点仍是 reviewer 复核 §149 后由 reviewer 通知用户；本轮**不通知用户、不改桌面 .lnk、不重打包、不动 v2.0/2.1/2.2 与 v2.3**。\n"
        "- **证据（结果文件 → 原始字段）**：`results/app/app339_v23_verify_final.json` → `items`（`zip_sha`/`unzip_check`/`gui`/`cli` 均 PASS、"
        "`blacklist=UNKNOWN`）／`artifacts` **20 项**；`app332_v23_zip_sha.json` → `sha256=4b4a977a…cbfed`／`bytes=11235945990`／"
        "`n_zip_entries=14320`；`app337_v23_cli_rerun.json` → `verdict=PASS`／`tts_final_stats.submitted=70`／"
        "`zero_segment_check.n_bad_rows=0`。本轮**未打包、未产出新交付物、未写「已交付」**。\n"
        "- **半交付／环境巡检（实测字段，见巡检 JSON）**：`git` → `head=4f0e931`／`branch=main`／`ahead=0` ⇒ 上轮 69 文件已普通 push、"
        "**无半交付**；`machine_lock.exists=false`；`prior_background_pids` 两条 PID 17220／7396 均由 `ctypes OpenProcess` "
        "**`verdict=DEAD_err87`** 确证死 ⇒ 无孤儿锁、无登记 PID。工作区 `n_worktree_changes=" + str(len(st_lines)) +
        "` 且 `corrections_file_modified_in_worktree=true` ⇒ 本轮**逐文件 `git add`**，绝不 `git add -A`、绝不提交纠偏文件、不吞 ASR/MT/TTS 其它模块改动。\n"
        "- **收尾复核（步骤 4）**：`CORRECTIONS_APP.md` 开工 SHA `d80ad25d1da40…c5dd9a`／**227 215 B**／mtime "
        "**2026-11-07 14:51:02**／**81 条**；收尾重取 `close_fingerprint` 与 `open_fingerprint` 逐项相同"
        "（`corrections_open_equals_close=PASS`）⇒ reviewer 本轮**未追加新条目**，可如实写 SHA 零改动；全程只读、未改、未提交。\n"
        "- **本轮产物**（文件数／mtime／字节数／SHA256 全部落盘实测）：\n\n"
        "  | 产物 | 用途 | 文件数 | mtime | 字节数 | SHA256 |\n"
        "  |---|---|---|---|---|---|\n"
        "  | `status/archive/STATUS_APP_sec149_20261107.md` | §149 正文整块逐字归档（APP-052④ 压缩） | 1 | " + arch_meta["mtime"] +
        " | " + str(arch_meta["bytes"]) + " | `" + arch_meta["sha256"] + "` |\n"
        "  | `results/app/app341_app_patrol_20261107.json` | 本轮巡检事实记录（指纹／编号／git／锁／PID／" + str(len(checks)) +
        " 项自检） | 1 | " + pj_meta["mtime"] + " | " + str(pj_meta["bytes"]) + " | `" + pj_meta["sha256"] + "` |\n\n"
        "- **纪律**：纯 CPU 静态巡检；未建 `MACHINE_LOCK`、未占设备、未在 CPU 跑推理或测速、未调 MiniMax；"
        "未打包／未打 zip／未改客户包与 .lnk／未 `--same-version`／未 force push。`last_ack` 保持 **APP-081**"
        "（无更大编号可推），「更新时间」取 `Get-Date` 实测 " + now + "。\n"
    )

    h_time_old = "更新时间: 2026-11-07 17:14:32"
    h_time_new = "更新时间: " + now
    ck("header_time_anchor_unique", old.count(h_time_old) == 1)

    mt = re.search(r"(?m)^当前任务: .*$", old)
    old_task = mt.group(0)
    new_task = (
        "当前任务: **§150 巡检无新纠偏（last_ack=APP-081 = 全文最大编号 081，新增条目 0）｜"
        "APP-081 第 5 点仍停在「需等 reviewer 复核」节点：§149 的 v2.3 全套验收原始结果已落盘，"
        "按 APP-081 第 6 点不自创任务、不自行推进；当前节点 = reviewer 复核 §149 后由 reviewer 通知用户**"
    )
    ck("header_task_anchor_unique", old.count(old_task) == 1)

    mc = re.search(r"(?m)^已压缩: .*$", old)
    old_cmp = mc.group(0)
    new_cmp = old_cmp + "｜**§150 压缩**：§149 正文整块逐字归档 ⇒ `status/archive/STATUS_APP_sec149_20261107.md`（块 SHA256 `" + arch_meta["sha256"] + "`）"
    ck("header_compressed_anchor_unique", old.count(old_cmp) == 1)

    new = old
    new = new.replace(h_time_old, h_time_new, 1)
    new = new.replace(old_task, new_task, 1)
    new = new.replace(old_cmp, new_cmp, 1)
    new = new.replace(sec149, quick + "\n" + sec150, 1)
    new_b = new.encode("utf-8")

    # ---------- E. 写前自检 ----------
    rev = new
    rev = rev.replace(h_time_new, h_time_old, 1)
    rev = rev.replace(new_task, old_task, 1)
    rev = rev.replace(new_cmp, old_cmp, 1)
    rev = rev.replace(quick + "\n" + sec150, sec149, 1)
    ck("reverse_restore_equals_old_full_text", rev == old, len(rev))
    ck("sec141_verbatim_preserved", sec141 in new and sec142 in new)
    ck("archive_block_not_lost", arch_b.decode("utf-8") in open(ARCH, "rb").read().decode("utf-8"))
    ck("sections_not_decreased",
       len(re.findall(r"(?m)^## §\d+", new)) == len(re.findall(r"(?m)^## §\d+", old)) + 1,
       len(re.findall(r"(?m)^## §\d+", new)))
    ck("new_status_lf_only", b"\r\n" not in new_b)
    n_lines = new_b.count(b"\n") + 1
    ck("status_limit_40000B_300L", len(new_b) <= 40000 and n_lines <= 300,
       "%d B / %d L" % (len(new_b), n_lines))
    ck("sec150_present_once", new.count("## §150 ") == 1)
    ck("last_ack_unchanged", "last_ack: APP-081" in new)
    ck("corrections_never_modified_by_this_script", corr_fp() == close_fp)

    # ---------- F. 原子替换 + 写后逐字节复核 ----------
    tmp = STAT + ".tmp_app341"
    try:
        with open(tmp, "wb") as f:
            f.write(new_b)
        os.replace(tmp, STAT)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)
    disk = open(STAT, "rb").read()
    ck("status_disk_byte_identical", disk == new_b, len(disk))
    final_corr = corr_fp()
    ck("final_corrections_still_unchanged", final_corr == OPEN_FP, final_corr)

    print("NOW_GET_DATE", now)
    print("STATUS_BEFORE_BYTES_LINES", len(old_b), old_b.count(b"\n") + 1)
    print("STATUS_AFTER_BYTES_LINES", len(disk), disk.count(b"\n") + 1)
    print("STATUS_AFTER_SHA256", sh(disk))
    print("ARCHIVE", json.dumps(arch_meta, ensure_ascii=False))
    print("PATROL_JSON", json.dumps(pj_meta, ensure_ascii=False))
    print("CHECKS", len(checks), "PASS", sum(1 for c in checks if c["pass"]),
          "FAIL", sum(1 for c in checks if not c["pass"]))
    print("FINAL_CORRECTIONS", json.dumps(final_corr, ensure_ascii=False))


if __name__ == "__main__":
    main()

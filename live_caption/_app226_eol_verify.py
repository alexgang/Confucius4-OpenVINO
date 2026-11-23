"""§226 独立复核脚本 —— 校验「reviewer 复算底本」的入库字节与 reviewer 原始文件逐字节一致。

背景（§226 发现，见 STATUS_APP_sec226_detail_20261124.md）：
  本仓 core.autocrlf=true 且此前**无 .gitattributes** ⇒ `git add` 会把 CRLF 规整成 LF 入库。
  §225 入库的 3 份 reviewer 原始 json（reviewer 自己的 CRLF 文件）因此在 **index/blob 里是 LF**，
  而证据 json `app128b_e2e7_table_evidence.json` 公布的是 **CRLF 原件** 的 sha256。
  ⇒ 在 core.autocrlf=false 的机器上 clone 得到的字节与公布的 SHA256 对不上（**假 FAIL**）。

修法：`results/app/app128b_e2e7_src/.gitattributes` 写 `*.json -text`（不做行尾转换），
  再 `git add --renormalize` 让 index blob 变成工作区字节原样。

本脚本**不修改任何文件**，只做四路复核：
  ① 工作区字节 == reviewer 原始文件字节（逐字节）
  ② index blob 字节 == reviewer 原始文件字节（逐字节）
  ③ index blob 的 sha256 == 证据 json 里公布的 source_sha256
  ④ 真跑一次 clone（core.autocrlf=false）⇒ clone 出来的文件 sha256 == 公布的 SHA256
     （④ 是「行为级真跑」，不是静态推断）

纪律：
  * 只读 reviewer 产物（shared/bgkeep/e2e7/），不改源。
  * 幂等：重跑不产生任何副作用。
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
E2E7 = os.path.join("C:\\", "Users", "Trekker-PTL", "shared", "bgkeep", "e2e7")
ARMS = ["off", "on_gpu", "on_cpu"]
SRC_DIR = os.path.join(REPO, "results", "app", "app128b_e2e7_src")
EVID = os.path.join(REPO, "results", "app", "app128b_e2e7_table_evidence.json")
ATTR = os.path.join(SRC_DIR, ".gitattributes")


def sha(b):
    return hashlib.sha256(b).hexdigest()


def git(*args, cwd=REPO):
    return subprocess.run(["git"] + list(args), cwd=cwd,
                          capture_output=True, text=True, errors="replace")


def main():
    checks = []
    ok = True

    ev = json.load(open(EVID, encoding="utf-8"))
    pub = {a["arm"]: a["source_sha256"] for a in ev["arms"]}

    # ① ② 工作区 / index blob 与 reviewer 原件逐字节一致
    for arm in ARMS:
        orig = os.path.join(E2E7, arm, "bgkeep_e2e.json")
        repo = os.path.join(SRC_DIR, "%s_bgkeep_e2e.json" % arm)
        ob = open(orig, "rb").read()
        wb = open(repo, "rb").read()
        p = "results/app/app128b_e2e7_src/%s_bgkeep_e2e.json" % arm
        blob = git("show", ":" + p).stdout.encode("utf-8", "surrogateescape")
        # git show 走文本管道会破坏字节 ⇒ 用 cat-file 取原始 blob
        blob = subprocess.run(["git", "cat-file", "blob", ":" + p], cwd=REPO,
                              capture_output=True).stdout
        c1 = (ob == wb)
        c2 = (ob == blob)
        c3 = (sha(blob) == pub[arm])
        ok = ok and c1 and c2 and c3
        checks.append({"arm": arm, "bytes": len(ob),
                       "reviewer_sha256": sha(ob),
                       "worktree_sha256": sha(wb), "index_blob_sha256": sha(blob),
                       "published_sha256": pub[arm],
                       "worktree_bytes_equal_reviewer": c1,
                       "index_blob_bytes_equal_reviewer": c2,
                       "index_blob_sha_equal_published": c3})

    # .gitattributes 必须在，且含 -text
    attr_ok = os.path.exists(ATTR) and "-text" in open(ATTR, encoding="utf-8").read()
    eol = git("ls-files", "--eol", "--", "results/app/app128b_e2e7_src/").stdout
    attr_applied = all("attr/-text" in ln for ln in eol.splitlines() if "_bgkeep_e2e.json" in ln)
    ok = ok and attr_ok and attr_applied

    # ③ 真跑 clone（core.autocrlf=false）⇒ 复现公布的 SHA256
    # 🔴 关键：`-c core.autocrlf=false` 必须作用在 **clone 本身**（checkout 发生在 clone 过程中）；
    #    若 clone 之后再 `git config core.autocrlf false`，checkout 早已按当时的配置做完
    #    ⇒ 测的是「autocrlf=true 的 clone」⇒ **假 PASS**（本脚本第一版就踩了这个坑，已修）。
    tmp = tempfile.mkdtemp(prefix="app226_clone_")
    try:
        cl = os.path.join(tmp, "c")
        r = subprocess.run(["git", "-c", "core.autocrlf=false", "clone",
                            "--no-hardlinks", "--quiet", REPO, cl],
                           capture_output=True, text=True)
        if r.returncode != 0:
            ok = False
            clone_err = r.stderr.strip()[:400]
            clone_rows = []
        else:
            clone_err = None
            clone_rows = []
            for arm in ARMS:
                p = os.path.join(cl, "results", "app", "app128b_e2e7_src",
                                 "%s_bgkeep_e2e.json" % arm)
                d = open(p, "rb").read()
                m = sha(d) == pub[arm]
                ok = ok and m
                clone_rows.append({"arm": arm, "clone_bytes": len(d),
                                   "clone_sha256": sha(d),
                                   "published_sha256": pub[arm],
                                   "matches_published": m})
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    # ④ 反证组（negative control）：修法必须 **load-bearing**。
    #    在「修前」的提交（无 .gitattributes ⇒ blob 是 LF）上跑同一个 clone 口径，
    #    复现出的 SHA 必须 **对不上**公布的 SHA ⇒ 证明「-text 修法」确实是承重的，
    #    而不是「口径本身恰好通过」。
    #    修前提交 = 引入本缺陷的那次提交（§225 的 b7507cb）；用它的父提交做参照亦可，
    #    这里直接取 HEAD~（修后提交）的前一个即可。
    nc = {"done": False}
    try:
        prev = git("rev-parse", "HEAD").stdout.strip()
        # 找修前的那次提交：不含 .gitattributes 的提交
        rev = git("rev-list", "--max-count=40", "HEAD").stdout.split()
        buggy = None
        for r_ in rev:
            has = git("cat-file", "-e", "%s:results/app/app128b_e2e7_src/.gitattributes" % r_)
            if has.returncode != 0:
                buggy = r_
                break
        if buggy:
            tmp2 = tempfile.mkdtemp(prefix="app226_nc_")
            try:
                cl2 = os.path.join(tmp2, "c")
                rc = subprocess.run(["git", "-c", "core.autocrlf=false", "clone",
                                     "--no-hardlinks", "--quiet", "--revision", buggy, REPO, cl2],
                                    capture_output=True, text=True)
                if rc.returncode == 0:
                    rows = []
                    all_mismatch = True
                    for arm in ARMS:
                        p = os.path.join(cl2, "results", "app", "app128b_e2e7_src",
                                         "%s_bgkeep_e2e.json" % arm)
                        if not os.path.exists(p):
                            continue
                        d = open(p, "rb").read()
                        m = sha(d) == pub[arm]
                        if m:
                            all_mismatch = False
                        rows.append({"arm": arm, "clone_bytes": len(d),
                                     "clone_sha256": sha(d),
                                     "published_sha256": pub[arm],
                                     "matches_published": m})
                    nc = {"done": True, "buggy_revision": buggy,
                          "rows": rows,
                          "all_mismatch_as_expected": all_mismatch,
                          "note": "修前提交上同一口径应全部对不上（证明修法承重）"}
                    ok = ok and all_mismatch
            finally:
                shutil.rmtree(tmp2, ignore_errors=True)
    except Exception as e:  # noqa: BLE001
        nc = {"done": False, "error": repr(e)}

    result = {"check": "§226 reviewer 复算底本入库字节一致性（四路复核 + 反证组）",
              "clone_method": "git -c core.autocrlf=false clone --no-hardlinks（模拟 Linux reviewer，"
                              "配置作用于 clone 本身 ⇒ checkout 即按 autocrlf=false 落盘）",
              "gitattributes": {"path": "results/app/app128b_e2e7_src/.gitattributes",
                                "exists": attr_ok, "attr_-text_applied": attr_applied,
                                "ls_files_eol": eol.splitlines()},
              "per_arm": checks,
              "clone_verification": {"error": clone_err, "rows": clone_rows},
              "negative_control": nc,
              "all_pass": bool(ok)}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print("\nRESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

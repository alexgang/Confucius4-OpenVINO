"""Build a per-arm runner from run_bgkeep_v5_app.ps1.

Why: the reviewer's run_bgkeep_v5.ps1 runs all 7 arms in ONE PowerShell process
(~20 min: 7 x [bridge load ~43 s + clip run + tail wait]). The background-task
timeout of the tool kills the process at ~2 min, which kills the bridge mid-arm
AND leaks the machine lock (the finally block never runs).

Fix: same script, but with an -Arms filter so each invocation runs a subset.
Run-Arm (the per-arm body: bridge start, e2e call, memory report, bridge stop)
is copied BYTE-IDENTICALLY. The only added lines are the parameter and the two
arm filters.

Derived from: shared/bgkeep/run_bgkeep_v5_app.ps1  (which is
shared/bgkeep/run_bgkeep_v5.ps1 with ONLY the $lock path changed).
"""
import difflib
import os

SRC = r"C:\Users\Trekker-PTL\shared\bgkeep\run_bgkeep_v5_app.ps1"
DST = r"C:\Users\Trekker-PTL\shared\bgkeep\run_bgkeep_v5_app_arm.ps1"

src = open(SRC, encoding="utf-8").read()

# 1) add the -Arms parameter next to the existing -clipDev parameter
old_param = 'param([string]$clipDev = "GPU.0")'
new_param = ('param([string]$clipDev = "GPU.0",\n'
             '      [string]$Arms = "all",\n'
             '      [string]$Tag = "v5")')
assert src.count(old_param) == 1, "param anchor not unique"
out = src.replace(old_param, new_param)

# 2) filter the two arm loops (Run-Arm body itself is untouched)
old_clip = ('  foreach ($c in @(@("cs2","zh"), @("s1","zh"), @("s2","en"), @("tuffy","en"))) {\n'
            '    Run-Arm ("clip_" + $c[0]) $clipDev "$clips\\$($c[0]).wav" $c[1] @() 30 "A"\n'
            '  }')
new_clip = ('  foreach ($c in @(@("cs2","zh"), @("s1","zh"), @("s2","en"), @("tuffy","en"))) {\n'
            '    $an = "clip_" + $c[0]\n'
            '    if (($Arms -eq "all") -or ($Arms -split "," -contains $an)) {\n'
            '      Run-Arm $an $clipDev "$clips\\$($c[0]).wav" $c[1] @() 30 "A"\n'
            '    }\n'
            '  }')
assert out.count(old_clip) == 1, "clip loop anchor not unique"
out = out.replace(old_clip, new_clip)

old_clone = ('  foreach ($c in @(@("s1","zh"), @("s2","en"), @("cs2","zh"))) {\n'
             '    Run-Arm ("clone_" + $c[0]) $clipDev "$clips\\$($c[0]).wav" $c[1] @() 40 "clone"\n'
             '  }')
new_clone = ('  foreach ($c in @(@("s1","zh"), @("s2","en"), @("cs2","zh"))) {\n'
             '    $an = "clone_" + $c[0]\n'
             '    if (($Arms -eq "all") -or ($Arms -split "," -contains $an)) {\n'
             '      Run-Arm $an $clipDev "$clips\\$($c[0]).wav" $c[1] @() 40 "clone"\n'
             '    }\n'
             '  }')
assert out.count(old_clone) == 1, "clone loop anchor not unique"
out = out.replace(old_clone, new_clone)

# 3) per-invocation lock tag so several invocations never collide, and the
#    finally-block release check must match that tag
old_tag = '$tag   = "app bgkeep e2e v5 " + (Get-Date -Format s)'
new_tag = '$tag   = "app bgkeep e2e " + $Tag + " " + (Get-Date -Format s)'
assert out.count(old_tag) == 1, "tag anchor not unique"
out = out.replace(old_tag, new_tag)

open(DST, "w", encoding="utf-8", newline="").write(out)

d = list(difflib.unified_diff(src.splitlines(), out.splitlines(), lineterm="", n=1))
print("diff vs run_bgkeep_v5_app.ps1:")
for x in d:
    print(x)
print("DST bytes", os.path.getsize(DST))


# the Run-Arm body must be byte-identical
def body(text):
    i = text.index("function Run-Arm")
    j = text.index("$waited = 0")
    return text[i:j]


assert body(src) == body(out), "Run-Arm body changed!"
print("VERIFY: Run-Arm body byte-identical -> OK")

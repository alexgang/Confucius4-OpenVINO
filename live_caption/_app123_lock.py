"""Acquire / release the shared MACHINE_LOCK atomically (App side).

Rule: the lock file is created with an ATOMIC create (O_CREAT|O_EXCL) so two
modules cannot both "take" it. Content: module name + PID + start time.
If it already exists we WAIT (never steal).

Usage:
    python _app123_lock.py acquire app
    python _app123_lock.py release app <pid>
"""
import os
import sys
import time

LOCK = r"C:\Users\Trekker-PTL\shared\MACHINE_LOCK"


def acquire(module, timeout_s=0):
    tag = "%s %d %s" % (module, os.getpid(),
                        time.strftime("%Y-%m-%dT%H:%M:%S"))
    t0 = time.time()
    while True:
        try:
            fd = os.open(LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            try:
                cur = open(LOCK, encoding="utf-8", errors="replace").read().strip()
            except Exception:
                cur = "(unreadable)"
            if timeout_s and (time.time() - t0) > timeout_s:
                print("LOCK BUSY: %s" % cur)
                return 10
            print("waiting for lock (held by: %s)" % cur, flush=True)
            time.sleep(30)
            continue
        except PermissionError:
            print("LOCK: cannot create %s (permission)" % LOCK)
            return 11
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(tag)
        print("LOCK ACQUIRED: %s" % tag)
        return 0


def release(module, pid):
    if not os.path.exists(LOCK):
        print("no lock to release")
        return 0
    try:
        cur = open(LOCK, encoding="utf-8", errors="replace").read().strip()
    except Exception:
        cur = ""
    if not cur.startswith(module + " "):
        print("lock is not ours (%s) -> NOT removing" % cur)
        return 3
    os.remove(LOCK)
    print("LOCK RELEASED: %s" % cur)
    return 0


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "acquire"
    if cmd == "acquire":
        mod = sys.argv[2] if len(sys.argv) > 2 else "app"
        tout = int(sys.argv[3]) if len(sys.argv) > 3 else 0
        sys.exit(acquire(mod, tout))
    elif cmd == "release":
        mod = sys.argv[2] if len(sys.argv) > 2 else "app"
        sys.exit(release(mod, int(sys.argv[3]) if len(sys.argv) > 3 else os.getpid()))
    print("usage: _app123_lock.py acquire <module> [timeout_s] | release <module> [pid]")
    sys.exit(2)

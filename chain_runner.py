#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Chain Runner - jalankan wm_pipeline2.py untuk beberapa folder secara berurutan.
Cocok untuk pemrosesan massal banyak folder foto monitoring.
"""

import subprocess
import sys
import time
import os
import json
import datetime
import hashlib
from pathlib import Path

# Python interpreter yang digunakan untuk menjalankan pipeline
PY = sys.executable

# Folder scratch untuk file sementara pipeline
S = Path(os.environ.get("WM_SCRATCH", Path.home() / ".wm_geoinject" / "scratch"))
S.mkdir(parents=True, exist_ok=True)

# Base folder yang berisi sub-folder foto (dari argumen atau env)
BASE = Path(os.environ.get("WM_BASE", Path.cwd()))

LOG = S / "chain.log"

# Daftar (nama_folder, nama_script_pipeline) - bisa diisi manual atau dari env
QUEUE_ENV = os.environ.get("WM_QUEUE", "")
if QUEUE_ENV:
    try:
        QUEUE = json.loads(QUEUE_ENV)
    except Exception:
        QUEUE = []
else:
    # Default kosong - user isi manual
    QUEUE = []

def log(m):
    line = "%s | %s" % (datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), m)
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")

def progress(folder):
    """-> (done, total)"""
    p = BASE / folder / "wm_ocr_log.jsonl"
    if not p.exists():
        return 0, 0
    n = sum(1 for l in open(p, encoding="utf-8") if l.strip())
    d = BASE / folder
    allf = [f for f in os.listdir(d)
            if f.upper().endswith((".JPG", ".JPEG")) and not f.startswith(".")]
    seen, uniq = set(), 0
    by_size = {}
    for f in allf:
        try:
            by_size.setdefault(os.path.getsize(os.path.join(d, f)), []).append(f)
        except OSError:
            pass
    for sz, grp in by_size.items():
        if len(grp) == 1:
            uniq += 1
            continue
        for f in grp:
            h = hashlib.md5()
            with open(os.path.join(d, f), "rb") as fh:
                h.update(fh.read())
            k = h.hexdigest()
            if k not in seen:
                seen.add(k)
                uniq += 1
    return n, uniq

def wait_for_idle(folder, timeout_h=12):
    stable = 0
    t0 = time.time()
    last = None
    while time.time() - t0 < timeout_h * 3600:
        done, total = progress(folder)
        cur = (done, total)
        if total and done >= total:
            stable += 1
            if stable >= 3:
                log("  %s idle & selesai (%d/%d)" % (folder, done, total))
                return True
        else:
            stable = 0
        if cur != last:
            log("  menunggu %s: %d/%d" % (folder, done, total))
            last = cur
        time.sleep(60)
    return False

def main():
    log("=" * 66)
    log("CHAIN START — %d folder" % len(QUEUE))

    for folder, script in QUEUE:
        sp = S / script
        if not sp.exists():
            log("SKIP %s: script tidak ada (%s)" % (folder, script))
            continue
        done, total = progress(folder)
        if total and done >= total:
            log("SKIP %s: sudah selesai (%d/%d)" % (folder, done, total))
            continue
        log("START %s  (%d/%d sudah diproses)" % (folder, done, total))
        t0 = time.time()
        try:
            r = subprocess.run([PY, str(sp), str(BASE / folder)],
                               capture_output=True, text=True)
            out = r.stdout or ""
            for ln in out.splitlines():
                if any(k in ln for k in ["Plan A (", "Plan B (", "Plan C (",
                                         "Total:", "duplikat", "Model usage",
                                         "sudah selesai:"]):
                    log("   " + ln.split("| ", 1)[-1])
            log("END %s (%.1f jam)" % (folder, (time.time() - t0) / 3600))
        except Exception as e:
            log("ERROR %s: %s" % (folder, str(e)[:200]))
    log("=" * 66)
    log("CHAIN DONE")

if __name__ == "__main__":
    main()

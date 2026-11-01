#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Progress Report - lajuan pemrosesan WM GeoInject untuk semua folder.
Digunakan untuk memantau progres OCR watermark + inject EXIF.
"""

import os
import json
import hashlib
import collections
import datetime
from pathlib import Path

BASE = Path(os.environ.get("WM_BASE", Path.cwd()))

# Daftar folder yang ingin dipantau (dari env atau default kosong)
FOLDERS_ENV = os.environ.get("WM_FOLDERS", "")
FOLDERS = [f.strip() for f in FOLDERS_ENV.split(",") if f.strip()] if FOLDERS_ENV else []


def uniq_count(d):
    """Jumlah file unik setelah filter duplikat (size-group + md5)."""
    try:
        allf = [f for f in os.listdir(d)
                if f.upper().endswith((".JPG", ".JPEG")) and not f.startswith(".")]
    except OSError:
        return 0, 0
    by_size = {}
    for f in allf:
        try:
            by_size.setdefault(os.path.getsize(os.path.join(d, f)), []).append(f)
        except OSError:
            pass
    seen, uniq = set(), 0
    for sz, grp in by_size.items():
        if len(grp) == 1:
            uniq += 1
            continue
        for f in grp:
            h = hashlib.md5()
            try:
                with open(os.path.join(d, f), "rb") as fh:
                    h.update(fh.read())
            except OSError:
                continue
            k = h.hexdigest()
            if k not in seen:
                seen.add(k)
                uniq += 1
    return len(allf), uniq


def main():
    if not FOLDERS:
        # Jika tidak ada daftar, scan semua subfolder di BASE
        if BASE.exists():
            FOLDERS.extend([f.name for f in BASE.iterdir() if f.is_dir()])

    rows = []
    grand = {"raw": 0, "uniq": 0, "A": 0, "B": 0, "C": 0}
    for folder in FOLDERS:
        d = BASE / folder
        raw, uniq = uniq_count(d)
        lj = d / "wm_ocr_log.jsonl"
        recs = []
        if lj.exists():
            recs = [json.loads(l) for l in open(lj, encoding="utf-8") if l.strip()]
        cnt = collections.Counter(r.get("plan") for r in recs)
        A, B, C = cnt.get("A", 0), cnt.get("B", 0), cnt.get("C", 0)
        done = len(recs)
        pct = (done / uniq * 100) if uniq else 0.0
        coords = set((r["lat"], r["lon"]) for r in recs if r.get("lat"))
        rows.append((folder, raw, uniq, done, pct, A, B, C, len(coords)))
        grand["raw"] += raw
        grand["uniq"] += uniq
        grand["A"] += A
        grand["B"] += B
        grand["C"] += C

    print("=" * 74)
    print("PROGRES OCR WATERMARK  —  %s" % datetime.datetime.now().strftime("%d-%m-%Y %H:%M"))
    print("=" * 74)
    print("%-20s %7s %7s %7s %8s %5s %5s %5s %6s" %
          ("FOLDER", "TOTAL", "UNIK", "SELESAI", "PROGRES", "A", "B", "C", "TITIK"))
    print("-" * 74)
    for folder, raw, uniq, done, pct, A, B, C, uc in rows:
        bar = "#" * int(pct / 2.5)
        print("%-20s %7d %7d %7d %7.1f%% %5d %5d %5d %6d" %
              (folder, raw, uniq, done, pct, A, B, C, uc))
        print("%-20s |%-31s|" % ("", bar))
    print("-" * 74)
    gd = grand["A"] + grand["B"] + grand["C"]
    gpct = (gd / grand["uniq"] * 100) if grand["uniq"] else 0
    print("TOTAL: %d foto (unik %d) | selesai %d = %.1f%%" %
          (grand["raw"], grand["uniq"], gd, gpct))
    print("  Plan A (GPS diinjek): %d" % grand["A"])
    print("  Plan B (tanpa WM)   : %d" % grand["B"])
    print("  Plan C (perlu baca) : %d" % grand["C"])
    print("  Titik GPS unik total: %d" % len(set()))
    print("=" * 74)


if __name__ == "__main__":
    main()

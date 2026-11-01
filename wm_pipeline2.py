#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WM GeoInject Pipeline v2 - OCR Watermark GPS + Injek EXIF
=========================================================
Plan A : WM ada, koordinat terbaca  -> _WM_GEOTAGGED  (GPS diinjek ke EXIF)
Plan B : tidak ada WM                -> _WM_TANPA_WM
Plan C : WM ada, GPS tidak terbaca   -> _WM_PERLU_BACA_MANUAL

Jalankan:  python wm_pipeline2.py <folder_foto>
Resume   :  jalankan ulang command yang sama (foto selesai akan di-skip)

Sebelum menjalankan:
  1. Salin .env.example -> .env
  2. Isi API_KEY di .env
  3. Pastikan piexif, Pillow terinstall
"""

import os
import re
import json
import base64
import subprocess
import time
import shutil
import datetime
import csv
import sys
import hashlib
from pathlib import Path
from PIL import Image, ImageOps

try:
    import piexif
except ImportError:
    sys.exit("ERROR: piexif tidak ada. Install: pip install piexif Pillow")

# ===================== KONFIGURASI =====================
# Folder foto diterima via argumen command line; default = folder saat ini
SRC = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()

OK     = SRC / "_WM_GEOTAGGED"
NOWM   = SRC / "_WM_TANPA_WM"
PEND   = SRC / "_WM_PERLU_BACA_MANUAL"
LOGF   = SRC / "pipeline.log"
LOGJ   = SRC / "wm_ocr_log.jsonl"
REPO   = SRC / "report.csv"
REPEND = SRC / "report_pending.csv"
SCRATCH = Path(os.environ.get("WM_SCRATCH", Path.home() / ".wm_geoinject" / "scratch"))

for D in (OK, NOWM, PEND, SCRATCH):
    D.mkdir(parents=True, exist_ok=True)

# ===================== MODEL RANKING =====================
# Model gratis yang support vision (urutkan sesuai keandalan)
MODEL_RANK = [
    os.environ.get("WM_MODEL_PRIMARY", "ciora-vision-free"),
    os.environ.get("WM_MODEL_FALLBACK1", "dots-studio/dots-3-note-preview"),
    os.environ.get("WM_MODEL_FALLBACK2", "ciora-coding-free"),
]

PROMPT = (
    "This photo has a GPS watermark overlay near the bottom edge.\n"
    "Answer with ONLY these 4 lines, no explanation:\n"
    "WM: <YES or NO>\n"
    "LAT: <latitude exactly as printed, or NONE>\n"
    "LON: <longitude exactly as printed, or NONE>\n"
    "DATE: <date and time exactly as printed, or NONE>\n\n"
    "Rules:\n"
    "- WM is YES only if you can actually SEE a text block in that area.\n"
    "- If the text block is visible but numbers are blurry/faint/washed out, "
    "set WM: YES and LAT/LON: NONE.\n"
    "- Only set WM: NO if there is no text block there at all.\n"
)

RE_LAT = re.compile(r'(\d{1,3}\.\d{4,9})\s*[°º]?\s*([NS])', re.I)
RE_LON = re.compile(r'(\d{1,3}\.\d{4,9})\s*[°º]?\s*([EW])', re.I)

MODEL_IDX = 0
MODEL_STATS = {}

# Muat API key dari .env di folder projek
def load_env(env_path: Path = Path(".env")):
    env = {}
    if env_path.exists():
        with open(env_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip().strip('"').strip("'")
    return env

_env = load_env()
API_KEY = _env.get("WM_API_KEY", "")

def deg_to_dms(deg):
    a = abs(deg)
    d = int(a)
    m = int((a - d) * 60)
    s = (a - d - m / 60.0) * 3600
    return ((d, 1), (m, 1), (int(round(s * 100)), 100))

def ask_model(b64, model, tries=3):
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": [
            {"type": "text", "text": PROMPT},
            {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + b64}},
        ]}],
        "max_tokens": 4000,
    }
    pf = SCRATCH / "_p2.json"
    with open(pf, "w", encoding="utf-8") as f:
        json.dump(payload, f)

    out = SCRATCH / "_r2.json"
    for _ in range(tries):
        if out.exists():
            out.unlink()
        subprocess.run(
            ["curl", "-s", "-m", "180", "-X", "POST",
             os.environ.get("WM_API_ENDPOINT", "https://ciora.id/v1/chat/completions"),
             "-H", "Content-Type: application/json",
             "-H", "Authorization: Bearer " + API_KEY,
             "-d", "@" + str(pf), "-o", str(out)],
            check=False,
        )
        if out.exists() and out.stat().st_size > 200:
            try:
                j = json.load(open(out, encoding="utf-8"))
                txt = (j["choices"][0]["message"].get("content") or "").strip()
                if txt:
                    return txt
            except Exception:
                pass
        time.sleep(4)
    return None

def read_watermark(img_path):
    im = ImageOps.exif_transpose(Image.open(img_path)).convert("RGB")
    W, H = im.size
    outs = []
    for box in [
        (0, int(H * 0.70), W, H),
        (0, int(H * 0.55), W, int(H * 0.90)),
        (0, int(H * 0.60), int(W * 0.60), H),
    ]:
        c = im.crop(box)
        c.thumbnail((1400, 1400), Image.LANCZOS)
        outs.append(c)
    w = max(o.width for o in outs)
    h = sum(o.height for o in outs) + 20 * (len(outs) - 1)
    canvas = Image.new("RGB", (w, h), (20, 20, 20))
    y = 0
    for o in outs:
        canvas.paste(o, (0, y))
        y += o.height + 20
    canvas.thumbnail((1400, 1600), Image.LANCZOS)
    tmp = SCRATCH / "_c2.jpg"
    canvas.save(tmp, quality=88)
    return base64.b64encode(open(tmp, "rb").read()).decode()

def parse_response(txt):
    """-> (wm_seen: bool, lat, lon, date)"""
    if not txt:
        return False, None, None, None
    low = txt.upper()
    wm_yes = re.search(r'WM\s*:\s*(YES|TRUE|1)', txt, re.I)
    wm_no = re.search(r'WM\s*:\s*(NO|FALSE|0|NONE)', txt, re.I)
    seen = True if wm_yes else (False if wm_no else ("WM:" in low))

    lat_m = RE_LAT.search(txt)
    lon_m = RE_LON.search(txt)
    lat = float(lat_m.group(1)) if lat_m else None
    lon = float(lon_m.group(1)) if lon_m else None
    if lat_m and lat_m.group(2).upper() == "S":
        lat = -lat
    if lon_m and lon_m.group(2).upper() == "W":
        lon = -abs(lon)

    d_m = re.search(r'DATE\s*:(.+)', txt, re.I)
    date = d_m.group(1).strip() if d_m else None
    return seen, lat, lon, date

def inject_gps(src, dst, lat, lon):
    im = Image.open(src)
    with open(src, "rb") as f:
        ex = piexif.load(f.read())
    if "Exif" not in ex:
        ex["Exif"] = {}
    dto = ex["Exif"].get(36867)
    if not dto:
        dto = datetime.datetime.fromtimestamp(os.path.getmtime(src)).strftime("%Y:%m:%d %H:%M:%S")
        ex["Exif"][36867] = dto.encode("utf-8")

    ex["GPS"] = {
        1: b"N" if lat >= 0 else b"S",
        2: deg_to_dms(lat),
        3: b"E" if lon >= 0 else b"W",
        4: deg_to_dms(lon),
    }
    exb = piexif.dump(ex)
    tmp = str(dst) + ".tmp.jpg"
    im.save(tmp, format="JPEG", exif=exb, quality=95)
    os.replace(tmp, dst)

def logit(msg):
    line = "%s | %s" % (datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), msg)
    print(line)
    with open(LOGF, "a", encoding="utf-8") as f:
        f.write(line + "\n")

def file_sig(fp):
    h = hashlib.md5()
    with open(fp, "rb") as fh:
        h.update(fh.read())
    return (os.path.getsize(fp), h.hexdigest())

def find_duplicates(names, src_dir):
    by_size = {}
    for n in names:
        fp = os.path.join(src_dir, n)
        try:
            by_size.setdefault(os.path.getsize(fp), []).append(n)
        except OSError:
            continue
    sigs = {}
    for sz, group in by_size.items():
        if len(group) == 1:
            sigs[group[0]] = (sz, "unique")
            continue
        for n in group:
            sigs[n] = (sz, file_sig(os.path.join(src_dir, n))[1])
    seen = {}
    keep, dups = [], {}
    for n in names:
        sz, hsh = sigs.get(n, (0, None))
        if hsh == "unique" or hsh is None:
            keep.append(n)
            continue
        if hsh in seen:
            dups[n] = seen[hsh]
        else:
            seen[hsh] = n
            keep.append(n)
    return keep, dups

# ===================== MAIN =====================
_all = sorted(
    f for f in os.listdir(SRC)
    if f.upper().endswith((".JPG", ".JPEG")) and not f.startswith(".")
)

_keep, _dupmap = find_duplicates(_all, SRC)
if _dupmap:
    _saved = sum(os.path.getsize(os.path.join(SRC, d)) for d in _dupmap
                 if os.path.exists(os.path.join(SRC, d)))
    logit("duplikat: %d file identik dilewati (hemat %.2f GB) -> diproses 1x"
          % (len(_dupmap), _saved / 1e9))
files = _keep
if OK.is_dir():
    files += [f for f in os.listdir(OK) if f.upper().endswith(".JPG") and f not in files]

logit("=" * 70)
logit("WM GEOINJECT v2 START | folder: %s | %d foto" % (SRC, len(files)))

for D in (OK, NOWM, PEND):
    for f in os.listdir(D):
        if ".tmp." in f:
            os.remove(os.path.join(D, f))
            logit("cleanup: hapus file .tmp -> %s" % f)

done = {}
if LOGJ.exists():
    for line in open(LOGJ, encoding="utf-8"):
        try:
            r = json.loads(line)
            done[r["file"]] = r
        except Exception:
            pass

def has_gps(p):
    try:
        with open(p, "rb") as fh:
            g = piexif.load(fh.read()).get("GPS", {})
        return bool(g.get(2) and g.get(4))
    except Exception:
        return False

repaired = 0
for fn, r in done.items():
    if r.get("plan") != "A":
        continue
    out = OK / fn
    if not out.exists() or not has_gps(out):
        done.pop(fn, None)
        if out.exists():
            out.unlink()
        repaired += 1
if repaired:
    logit("repair: %d file Plan A tidak lengkap -> reprocess" % repaired)

pend = [r for r in done.values() if r.get("plan") == "C"]
to_do = [f for f in files if f not in done]

logit("sudah selesai: %d | perlu diproses: %d | Plan C menunggu manual: %d"
      % (len(done), len(to_do), len(pend)))
if not to_do:
    logit("TIDAK ADA YANG PERLU DIPROSES. Selesai.")
else:
    t0 = time.time()
    for i, fn in enumerate(to_do):
        sp = SRC / fn
        if not sp.exists():
            sp = OK / fn
        if not sp.exists():
            logit("SKIP %s: file tidak ditemukan" % fn)
            continue

        MODEL_IDX = 0
        seen, lat, lon, date = False, None, None, None
        txt = None
        b64 = None
        for _mi, m in enumerate(MODEL_RANK):
            MODEL_IDX = _mi
            try:
                if b64 is None:
                    b64 = read_watermark(sp)
                txt = ask_model(b64, m)
            except Exception:
                txt = None
            if txt:
                seen, lat, lon, date = parse_response(txt)
                if seen or lat is not None:
                    break
                if _mi < len(MODEL_RANK) - 1:
                    continue

        if not seen and lat is None:
            for _mi, m in enumerate(MODEL_RANK):
                MODEL_IDX = _mi
                try:
                    if b64 is None:
                        b64 = read_watermark(sp)
                    t2 = ask_model(b64, m)
                except Exception:
                    continue
                if t2 and re.search(r'WM\s*:\s*(YES|TRUE)', t2, re.I):
                    seen = True
                    d2 = re.search(r'DATE\s*:(.+)', t2, re.I)
                    date = d2.group(1).strip() if d2 else date
                    txt = t2
                    break

        plan = "A" if (seen and lat and lon) else ("C" if seen else "B")
        dst = {"A": OK, "B": NOWM, "C": PEND}[plan]
        try:
            if plan == "A":
                inject_gps(sp, dst / fn, lat, lon)
            else:
                shutil.copy2(sp, dst / fn)
        except Exception as e:
            logit("ERROR %s: %s" % (fn, str(e)[:150]))
            plan = "C"
            try:
                shutil.copy2(sp, PEND / fn)
            except Exception:
                pass

        r = {
            "file": fn, "plan": plan, "lat": lat, "lon": lon, "date": date,
            "model": MODEL_RANK[MODEL_IDX] if txt else None,
            "ts": datetime.datetime.now().isoformat(),
        }
        MODEL_STATS.setdefault(r["model"], {"A": 0, "B": 0, "C": 0})
        MODEL_STATS[r["model"]][plan] += 1
        done[fn] = r
        with open(LOGJ, "a", encoding="utf-8") as f:
            f.write(json.dumps(r) + "\n")

        el = time.time() - t0
        logit("[%d/%d] %s Plan %s | lat=%s lon=%s | %s"
              % (i + 1, len(to_do), fn, plan, lat, lon, str(int(el)) + "s"))

    # ===================== LAPORAN =====================
    A = [r for r in done.values() if r.get("plan") == "A"]
    B = [r for r in done.values() if r.get("plan") == "B"]
    C = [r for r in done.values() if r.get("plan") == "C"]

    logit("=" * 70)
    logit("LAPORAN FOLDER: %s" % SRC)
    logit("  Plan A (WM terbaca, GPS diinjek): %d" % len(A))
    logit("  Plan B (tidak ada WM):              %d" % len(B))
    logit("  Plan C (WM ada, GPS belum ketemu): %d" % len(C))
    logit("  Total: %d" % (len(A) + len(B) + len(C)))
    logit("  Model usage: " + json.dumps(MODEL_STATS))

    with open(REPO, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["file", "plan", "lat", "lon", "date_from_wm", "model"])
        for r in sorted(done.values(), key=lambda x: x["file"]):
            w.writerow([r["file"], r["plan"], r["lat"], r["lon"],
                        r.get("date"), r.get("model")])

    with open(REPEND, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["file", "date_from_wm", "note"])
        for r in sorted(C, key=lambda x: x["file"]):
            w.writerow([r["file"], r.get("date"), "WM ada, koordinat belum terbaca"])

    logit("  -> %s" % REPO)
    logit("  -> %s" % REPEND)
    logit("=" * 70)

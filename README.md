# WM GeoInject Pipeline

Pipeline Python untuk menginjeksikan koordinat GPS dari watermark foto ke dalam EXIF.
Dibuat untuk dokumentasi monitoring rehab mangrove dan konservasi pesisir.

## Fitur

- **OCR Watermark**: Deteksi teks GPS (lat/lon/tanggal) dari watermark foto menggunakan model vision (Ciora, dll.)
- **3 Plan Pemrosesan**:
  - Plan A: WM terbaca + koordinat lengkap → GPS diinjek ke EXIF
  - Plan B: Tidak ada WM → dipindah ke folder terpisah
  - Plan C: WM ada tapi koordinat tidak lengkap → antrean baca manual
- **Deduplikasi**: Skip file duplikat berdasarkan MD5 (hemat kuota API)
- **Resume**: Bisa dijalankan ulang, foto yang selesai akan di-skip
- **Atomic Write**: Tulis file aman, tidak corrupt jika proses terhenti
- **EXIF Guard**: Menjaga Orientation dan metadata EXIF asli

## Struktur Folder

```
wm_geoinject/
├── wm_pipeline2.py          # Pipeline utama
├── run_folder.py            # Jalankan pipeline untuk satu folder
├── chain_runner.py          # Jalankan banyak folder berurutan
├── progress.py              # Laporan progres
├── .env.example             # Contoh konfigurasi environment
├── requirements.txt         # Dependensi Python
└── README.md                # File ini
```

## Instalasi

```bash
# Clone repo
git clone https://github.com/username/wm-geoinject.git
cd wm-geoinject

# Buat dan aktifkan venv
python -m venv venv
venv\Scripts\activate  # Windows
# atau: source venv/bin/activate  # Linux/Mac

# Install dependensi
pip install -r requirements.txt

# Salin contoh env dan isi API key
cp .env.example .env
# Edit .env, isi WM_API_KEY
```

## Cara Pakai

### 1. Jalankan untuk satu folder
```bash
python wm_pipeline2.py /path/to/foto/folder
```

Hasil akan dibuat di dalam folder tersebut:
- `_WM_GEOTAGGED/` — foto dengan GPS berhasil diinjek
- `_WM_TANPA_WM/` — foto tanpa watermark
- `_WM_PERLU_BACA_MANUAL/` — foto WM ada tapi koordinat tidak lengkap
- `report.csv` — laporan lengkap
- `wm_ocr_log.jsonl` — log proses (untuk resume)

### 2. Jalankan banyak folder (chain)
```bash
python chain_runner.py
```
Atau atur `WM_QUEUE` di `.env`.

### 3. Lihat progres
```bash
python progress.py
```

## Variabel Environment (.env)

| Variabel | Keterangan |
|----------|------------|
| `WM_API_KEY` | API key untuk model vision (wajib) |
| `WM_API_ENDPOINT` | Endpoint chat completions (default: https://ciora.id/v1/chat/completions) |
| `WM_SCRATCH` | Folder file sementara |
| `WM_BASE` | Folder induk foto |
| `WM_FOLDERS` | Daftar folder untuk progress (pisah koma) |
| `WM_MODEL_PRIMARY` | Model vision utama |
| `WM_MODEL_FALLBACK1` | Model fallback 1 |
| `WM_MODEL_FALLBACK2` | Model fallback 2 |

## Lisensi

MIT License

## Disclaimer

Tool ini menggunakan model vision eksternal untuk OCR watermark. Akurasi tergantung kualitas foto dan kejelasan watermark. Selalu verifikasi hasil GPS sebelum digunakan untuk keperluan resmi.

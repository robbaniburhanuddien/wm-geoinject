# 🌱 WM GeoInject — Panduan Pengguna

Selamat datang! WM GeoInject adalah alat bantu untuk **mengubah foto monitoring jadi foto berkoordinat (geotagged)** secara otomatis. Cocok untuk dokumentasi lahan, rehab mangrove, konservasi pesisir, dan keperluan GIS lainnya.

Dengan WM GeoInject, kamu nggak perlu mengetik koordinat satu per satu. Alat ini membaca watermark GPS yang sudah ada di foto, lalu menyisipkannya ke dalam EXIF foto agar bisa langsung dibuka di QGIS, ArcGIS, atau aplikasi peta lainnya.

---

## 📖 Apa yang Bisa Alat Ini Lakukan?

| Masalah | Solusi WM GeoInject |
|---------|---------------------|
| Foto monitoring punya watermark tapi belum ada koordinat EXIF | Baca watermark → injek GPS ke EXIF otomatis |
| Ribuan foto yang harus diproses satu per satu | Proses massal folder, deteksi duplikat, hemat waktu |
| Beberapa foto watermark-nya blur atau tidak lengkap | Dipisahkan ke folder `_PERLU_BACA_MANUAL` untuk dicek nanti |
| Takut proses terhenti di tengah jalan | Ada fitur resume — jalankan ulang, foto yang selesai tidak diproses lagi |

---

## 🚀 Mulai Cepat (5 Menit)

### 1. Siapkan folder foto
Kumpulkan semua foto JPG/JPEG yang mau diproses ke satu folder. Contoh:
```
D:\Foto Monitoring\Desa Mangrove Januari\
```

### 2. Salin dan isi konfigurasi
Salin `.env.example` menjadi `.env`, lalu isi `WM_API_KEY` dengan API key model vision yang kamu pakai (mis. Ciora Vision).

```env
WM_API_KEY=sk-contoh-ganti-dengan-api-key-mu
WM_API_ENDPOINT=https://ciora.id/v1/chat/completions
```

### 3. Install dependensi
```bash
pip install -r requirements.txt
```

### 4. Jalankan pipeline
```bash
python wm_pipeline2_clean.py "D:\Foto Monitoring\Desa Mangrove Januari"
```

Tunggu hingga selesai. Hasilnya akan muncul di dalam folder foto kamu:

| Folder | Isinya |
|--------|--------|
| `_WM_GEOTAGGED/` | Foto yang berhasil dibaca koordinatnya, GPS sudah diinjek ke EXIF |
| `_WM_TANPA_WM/` | Foto yang tidak ada watermarknya |
| `_WM_PERLU_BACA_MANUAL/` | Foto ada watermark, tapi koordinat belum terbaca |
| `report.csv` | Laporan lengkap hasil proses |
| `wm_ocr_log.jsonl` | Catatan proses (digunakan untuk melanjutkan lagi nanti) |

---

## 🧠 Cara Kerja Singkat

1. **Deteksi duplikat** — Foto yang isinya identik (berdasarkan ukuran + MD5) hanya diproses sekali. Hemat kuota API.
2. **Baca watermark** — Alat memotong bagian bawah foto (di mana watermark biasanya ada) dan mengirimkannya ke model vision (mis. Ciora Vision).
3. **Klasifikasi**:
   - **Plan A**: Watermark ada + koordinat lengkap → GPS diinjek ke EXIF.
   - **Plan B**: Tidak ada watermark → dipindah ke `_WM_TANPA_WM`.
   - **Plan C**: Ada watermark tapi koordinat tidak lengkap → dipindah ke `_PERLU_BACA_MANUAL`.
4. **Simpan hasil** — Setiap foto yang sudah diproses dicatat ke `wm_ocr_log.jsonl` agar nanti bisa dilanjutkan.

---

## 🔄 Proses Terhenti? Jangan Khawatir

Kalau komputer mati atau proses terhenti di tengah jalan, cukup jalankan **command yang sama lagi**:

```bash
python wm_pipeline2_clean.py "D:\Foto Monitoring\Desa Mangrove Januari"
```

Alat akan otomatis melewati foto yang sudah selesai dan melanjutkan dari tempat berhenti.

---

## 📊 Lihat Progres

Kalau kamu punya banyak folder dan ingin melihat progres keseluruhan:

```bash
python progress_clean.py
```

Ini akan menampilkan tabel sederhana: berapa foto sudah selesai, berapa yang perlu baca manual, dan berapa titik GPS unik yang sudah terkumpul.

---

## 🔗 Pemrosesan Banyak Folder (Opsional)

Kalau ada banyak folder foto yang ingin diproses secara berurutan, gunakan `chain_runner_clean.py`. Atur daftar folder di file `.env` melalui variabel `WM_QUEUE` atau `WM_FOLDERS`.

---

## ❓ Pertanyaan Umum (FAQ)

**Q: Kok ada foto yang masuk ke `_PERLU_BACA_MANUAL`?**  
A: Artinya watermark terdeteksi, tapi angka koordinatnya terlalu blur, kabur, atau terpotong. Silakan cek foto tersebut secara manual dan catat koordinatnya kalau perlu.

**Q: Apakah foto asli saya akan terhapus atau diubah?**  
A: Tidak. Foto asli tetap ada. Hasil diinjek GPS disimpan sebagai file baru di folder `_WM_GEOTAGGED/`.

**Q: Kenapa ada file `.env`? Apa isinya rahasia?**  
A: `.env` berisi API key kamu. **Jangan pernah upload `.env` ke GitHub** — sudah diatur di `.gitignore`. Upload hanya `.env.example` sebagai contoh.

**Q: Saya nggak pakai Ciora, bisa pakai model lain?**  
A: Bisa. Atur `WM_API_ENDPOINT` dan `WM_MODEL_PRIMARY` di `.env` sesuai dengan model vision yang kamu pakai.

---

## 🤝 Kontribusi & Kontak

Alat ini dibuat untuk membantu dokumentasi lahan dan konservasi. Kalau kamu menemukan bug atau punya ide fitur baru, silakan buat issue atau pull request di repo ini.

Semoga bermanfaat untuk lingkungan dan konservasi di tanah air! 🌿

---

> **Catatan:** Akurasi pembacaan koordinat tergantung kualitas foto dan kejelasan watermark. Selalu verifikasi hasil GPS sebelum digunakan untuk keperluan resmi atau pengambilan keputusan penting.
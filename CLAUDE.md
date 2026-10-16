# Cogan — petunjuk untuk Claude

Baca **`docs/WORK-AGREEMENT.md`** sebelum mengerjakan apa pun. Isinya aturan kerja (bagian A), peta pekerjaan berprioritas (C) dan checkpoint (E).

- **Mulai sesi / owner mengetik `lanjutkan`:** baca entri terbaru di bagian *E. Checkpoint*, lalu kerjakan langkah **Berikutnya** di sana atau item teratas yang belum selesai di bagian C.
- **Owner mengetik `checkpoint`:** ikuti aturan A15: tulis entri checkpoint (Selesai / Sedang berjalan / Berikutnya / Menunggu owner), perbarui status di bagian C, commit + push ke branch kerja, laporkan hash commit.
- Branch utama `dev`; perubahan masuk lewat PR. Workflow build kernel hanya dijalankan owner (A10); compile lokal boleh.
- Ruang lingkup kernel 6.1 saja (A11). Target perangkat owner: Xiaomi 14T Pro (rothko), lihat `docs/rothko.md`.
- Bahasa dokumen dan laporan: Indonesia; README dan rilis juga berbahasa Inggris.

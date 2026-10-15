# Kesepakatan Kerja & Peta Pekerjaan

Dokumen ini adalah sumber utama aturan kerja dan urutan prioritas. Owner cukup mengetik **`lanjutkan`**; pekerjaan diambil dari item teratas yang belum selesai di bagian *Peta Pekerjaan*.

## A. Aturan kerja

1. **Petakan dulu, kerjakan kemudian.** Semua pekerjaan tercatat di peta di bawah dengan prioritas (P0 tertinggi). Tidak ada pekerjaan di luar peta tanpa ditambahkan dulu.
2. **Tidak ada pekerjaan ganda.** Cek peta, checkpoint, dan run hijau sebelum mulai. Pengulangan cek/test **maksimal 2 kali** (idealnya 1 kali) per perubahan.
3. **Hemat sumber daya.** Gabungkan perubahan kecil dalam satu commit/push yang bermakna; hindari push beruntun yang hanya memicu CI berulang.
4. **CI selektif.**
   - Run yang sudah **hijau** dicatat sebagai bukti keberhasilan (ID run) dan tidak dijalankan ulang.
   - Run **merah**: baca log dulu, cari akar masalah, perbaiki, lalu jalankan **satu** run verifikasi. Tidak boleh "coba-coba" berulang.
   - Re-run hanya bila benar-benar perlu (mis. runner mati sebelum test berjalan).
5. **PR selektif.** Satu PR = satu topik, kecil, berbasis branch tujuan yang benar. Jangan membuka PR antar branch yang tidak punya riwayat bersama (penyebab "This pull is big, showing recent 250").
6. **Rapikan issue/PR/branch** secara berkala; yang tidak perlu ditutup dengan alasan. Tidak wajib segera, tapi tidak boleh menumpuk.
7. **Tidak ada yang terbengkalai.** Pekerjaan sulit boleh ditunda, tetapi tetap tercatat di peta dengan status dan alasan.
8. **Judul workflow harus sesuai isi pekerjaannya.** Ketidaksesuaian dicatat dan diperbaiki.
9. **Checkpoint secukupnya.** Hanya di akhir satu blok kerja yang berarti (bukan setiap langkah), ditulis di bagian *Checkpoint* dokumen ini.
10. Owner yang memicu build/release secara manual. Tidak ada flash, release, atau penghapusan production guard tanpa keputusan owner.

## B. Temuan audit (2026-10-15)

| # | Temuan | Dampak |
|---|--------|--------|
| T1 | `master` dan `dev` **tidak punya riwayat bersama** (root commit berbeda; master 351 commit, dev 50). | PR `dev → master` akan menampilkan ratusan commit / ±18k baris → "This pull is big". |
| T2 | Fix SUSFS di `master` (#25 fail-fast patch, #26 cek `.config` ketat) **belum ada di `dev`**. Di `dev`, `error()` tidak menghentikan build, jadi kegagalan SUSFS bisa lolos diam-diam. | Risiko build "hijau" tanpa SUSFS aktif. |
| T3 | 22 branch lama (PR #1–#24 sudah ditutup) masih ada, semuanya berbasis riwayat `master`, bukan `dev`. | Berantakan, membingungkan saat memilih basis PR. |
| T4 | PR #27 (draft) berbasis `master`, 76 commit, menyentuh `build.yml`/`build.sh` yang di `dev` sudah jauh berbeda. | Konflik besar; perlu dipilah, bukan di-merge apa adanya. |
| T5 | Workflow `Validate` jalan di **setiap push** (sudah 405 run), banyak hanya untuk commit dokumen. | Boros CI. |
| T6 | Run `Cogan Kernel Builder` #7 (38720157010) merah: input `KernelSU Next + SUSFS` sengaja diblok guard (`build.yml:140`). | **Bukan bug** — guard bekerja sesuai desain. Tidak perlu re-run. |
| T7 | Nama workflow `Cogan Manual Update` berada di file `cogan-smart-auto-update.yml`; `Upload artifacts to telegram` dinonaktifkan manual tapi masih ada. | Judul vs isi tidak selaras (aturan A8). |

## C. Peta pekerjaan (urut prioritas)

| ID | Prio | Pekerjaan | Status |
|----|------|-----------|--------|
| W1 | P0 | Port fix SUSFS #25 + #26 dari `master` ke `dev` (fail-fast patch & cek `.config` yang benar-benar menghentikan build). Uji lokal sekali. | Belum |
| W2 | P0 | Tetapkan **satu branch utama** (usulan: `dev` sebagai sumber kebenaran). Keputusan owner: (a) jadikan `dev` default & bekukan `master`, atau (b) samakan `master` ke `dev` sekali saja. Setelah itu PR hanya ke branch utama. | Butuh keputusan owner |
| W3 | P1 | Integrasi SUSFS 6.1: `git apply --check` patch kandidat BBG spinlock pada source asli, terapkan sekali, review jalur locking (lanjutan handoff `docs/validation/ksun-susfs-6.1-work-handoff.md`). | Belum |
| W4 | P1 | Lanjutan SUSFS 6.1: `pahole`, generate `.config` di direktori baru, jalankan resolved-config gate. Baru setelah lulus → izin owner untuk compile terisolasi. | Tertunda (bergantung W3) |
| W5 | P2 | Pilah PR #27: ambil hanya bagian yang masih relevan (sublevel opsional, DroidSpaces off) ke PR kecil baru berbasis `dev`; tutup #27 dengan alasan. | Belum |
| W6 | P2 | Hemat CI: tambahkan `paths-ignore` (`docs/**`, `**.md`) pada `validate.yml`. | Belum |
| W7 | P3 | Rapikan 22 branch lama (PR sudah ditutup) — hapus setelah owner setuju; branch berstatus *protected* perlu dibuka proteksinya dulu. | Butuh izin owner |
| W8 | P3 | Selaraskan nama workflow dengan file/isi (T7); putuskan hapus atau simpan workflow Telegram yang nonaktif. | Belum |
| W9 | P3 | Rapikan issue #2, #3 (roadmap) dan #19 (SUSFS): perbarui ringkasan status, tutup yang selesai. | **Selesai** 2026-10-15 — body ketiganya diganti checklist status; tidak ada yang layak ditutup (masih ada sisa pekerjaan) |

## D. Bukti hijau (tidak perlu diulang)

- Validate run 405 (`38707353627`) pada `dev@70f5b30` — hijau.
- Main-patch-only SUSFS: run `38691986084`, job `116279761088` — hijau (lihat handoff).

## E. Checkpoint

- **2026-10-15** — Kesepakatan kerja & audit selesai. Berikutnya: **W1**.

# Status lanjutan W64 — perbaikan WebUI Android, 2026-10-18

Owner melaporkan Power v1.1 **Gagal membaca** melalui screenshot. Penyebab berhasil direproduksi: regex pada `controls_json` berisi delimiter `/` tanpa escape di dalam character class. `mawk` menerima, tetapi one-true-awk/BusyBox gagal dan meninggalkan `"controls":,`. Pengujian companion sebelumnya memakai mawk, sehingga tidak menangkap cacat ini.

- Power **v1.1.1 / versionCode 3** memperbaiki delimiter; Thermal **v1.2.1 / versionCode 4** mendapat perbaikan error/retry WebUI yang sama. Setelan tersimpan dan riwayat tidak dihapus.
- **47 uji modul** lulus: 44 sebelumnya dijalankan dengan mksh + one-true-awk, tiga uji baru mencakup sembilan kombinasi mksh/dash/BusyBox ash × one-true-awk/mawk/BusyBox awk. Lima uji draft terpisah lulus. Validator dan root matrix lulus. CI kini memasang alat Android secara eksplisit.
- Kedua WebUI 360 px lulus memakai backend shell sebenarnya dengan mksh/one-true-awk dan sysfs/proc simulasi: respons JSON rusak memunculkan error persisten, Coba lagi memulihkan tampilan, exit nonzero dengan JSON sukses tetap ditolak; Simpan/Terapkan/Mulai/Henti/Reset tetap lulus.
- Paket: `Cogan-Power-Mode-v1.1.1.zip`, `Cogan-Thermal-Monitor-v1.2.1.zip`; CRC dan semua payload dicocokkan dengan source. Bukti/hash terbaru di `cogan-companion-bridge-validation.json`.
- Tetap memakai branch `feat/module-kernel-bridge` / PR #101. Kernel driver tidak berubah; bukti object ARM64 lama tetap berlaku, full Clang/FullLTO/link dan uji HP tetap belum selesai. Tidak menjalankan build Actions kernel, publikasi rilis atau flashing.

**Berikutnya:** tunggu Validate baru untuk patch ini; owner pasang ZIP pembaruan, reboot sekali, buka WebUI dan periksa data suhu/CPU/kernel serta tombol. PR kernel tetap Draft/HOLD sampai build penuh dan validasi berikutnya.

---

# Arsip status lanjutan W63 — 2026-10-18

Owner meminta **Lanjutkan** setelah checkpoint. Status kode: Power Mode v1.1 + Thermal Monitor v1.2 selesai diperbarui, dua ZIP tersimpan pada identitas file asal, dan source berada di `feat/module-kernel-bridge`.

- 44 uji modul lulus; kedua WebUI mobile diuji dengan skrip shell sebenarnya terhadap perangkat simulasi.
- Bridge ARM64 berhasil dikompilasi pada GKI 6.1.177 `8c24bbff`, target `drivers/misc/cogan_bridge.o`, `gki_defconfig`, GCC 13.3. Pemeriksaan native juga lulus. Tidak ada build penuh Clang/FullLTO, uji perangkat, workflow build kernel atau flashing.
- Lifecycle fallback ↔ QoS, stale lock lintas boot/PID reuse, penghormatan boost eksternal, pemulihan tertunda dan kegagalan simpan diperbaiki. Cooling device native dibaca tanpa proses eksternal tambahan; suhu datar/turun tidak menambah rem ganda.
- Dua ZIP satu tingkat sudah diperiksa: `Cogan-Power-Mode-v1.1.zip`, `Cogan-Thermal-Monitor-v1.2.zip`. Henti/Reset persisten; cas default baru/reset 95/90; riwayat Thermal dipertahankan.
- Bukti: `docs/validation/cogan-companion-bridge-validation.json`; panduan: `docs/cogan-companion-bridge.md`.

**Berikutnya:** periksa hasil Validate pada PR perubahan ini sebelum merge. Owner menjalankan satu build kernel bila source sudah siap; kernel lama tetap memakai sysfs/kandidat identitas belum terverifikasi. Uji HP setelah full compile/kompatibilitas lulus. Jangan menjalankan ulang bukti hijau tanpa perubahan atau alasan.

Catatan di bawah adalah arsip checkpoint awal dan tidak lagi menyatakan status terbaru.

---

# Checkpoint Cogan Companion Bridge — 2026-10-18 00:27 WIB

**STOP atas permintaan owner: `Checkpoint`.** Tidak melanjutkan pengembangan, PR, merge, workflow build, rilis atau flashing sampai owner memberi instruksi kerja yang jelas (`Lanjutkan`).

## Selesai / tersimpan sebagai WIP

- Repo: https://github.com/cogan17/Cogan ; branch kerja: `feat/module-kernel-bridge`; basis dev: `720b4da6375d4c4d66d99294ba740ab5ea8b187f` (PR #100).
- Dasar modul: Power Mode repo v1.0 (sama dengan lampiran), Thermal Monitor repo v1.1 (lebih baru dari lampiran v1.0, mempertahankan `run/latest` dan ringkasan per mode).
- Kode kandidat Power Mode **v1.1 / versionCode 2**, Thermal Monitor **v1.2 / versionCode 3**. **Bukan rilis siap flash.**
- Kode bridge built-in generik di `kernel-patches/cogan/cogan_bridge.c`: ABI 1 root-only, release compile-time `UTS_RELEASE`, `linux_banner`, fitur build, heartbeat Power/Thermal, CPUFreq MAX QoS tersendiri dengan lease + notifier lifecycle + deferrable expiry. Belum berhasil mengompilasi object driver.
- Installer overlay aditif `scripts/install_cogan_bridge.py`; kait `build.sh` setelah verifikasi replay terkunci dan sebelum defconfig; gate `CONFIG_COGAN_BRIDGE=y`; pelaporan fitur `Cogan Bridge`. Pin/manifest/guard upstream tidak diubah.
- Kedua modul memiliki helper `bridge.sh` identik, UI identitas asli vs uname + sumber/kepercayaan, heartbeat dan deteksi pasangan, cooling device, Simpan/Terapkan/Henti/Mulai/Reset. Power memakai readback kontrol, mode paksa berulang, snapshot/pemulihan perubahan milik modul dan berhenti persisten. Reset default cas 95/90; setelan lama dipertahankan saat upgrade. Reset Thermal mempertahankan riwayat/log.
- Panduan kandidat `docs/cogan-companion-bridge.md` dan README modul diperbarui. Masih perlu penyelarasan beberapa kalimat lama yang menjanjikan suhu tetap atau semua kontrol selalu kembali normal.
- Bukti lokal: **12 uji Power + 13 Thermal + 14 companion = 39 lulus**, root matrix lulus, 7 uji kernel_features lulus, validator 8 workflow / 21 shell / 48 Python lulus; kedua inline JS lolos parsing Node. Detail disimpan di `cogan-companion-bridge-checkpoint-tests.txt`.
- Uji tersebut lulus sebelum perubahan kecil terakhir pada penanganan kegagalan tulis konfigurasi dan label identitas ekspor Thermal; verifikasi selektif sesudah perubahan terakhir masih menunggu.

## Sedang berjalan / batas bukti

- Semua kode pengembangan ini masih WIP; tidak ada PR baru, merge, kernel Actions, rilis, ZIP pembaruan final, atau flashing dari sesi ini. File ZIP asal belum diganti.
- Compile lokal **belum mencapai object bridge**. Source untuk pemeriksaan API adalah `aosp-mirror/kernel_common` branch android14-6.1, commit `498f91c17b0822a09aede17d26a63bf8c6813725` (Makefile **6.1.155**, bukan target 6.1.177). Pemeriksaan config x86_64 berhasil memilih CPU_FREQ=y dan COGAN_BRIDGE=y. Ini tidak membuktikan target ARM64/GKI.
- Percobaan object berhenti saat persiapan host: `scripts/selinux/genheaders/genheaders.c:18: classmap.h: No such file or directory` karena sparse checkout belum memuat `security/selinux/include`. Percobaan menambah subtree terakhir gagal di sintaks: `git sparse-checkout add` tidak menerima `--no-cone` (mode no-cone sudah aktif). Jangan menganggap driver lolos compile.
- Browser Chromium tidak tersedia; unduhan Playwright menghasilkan arsip tidak valid, sehingga **belum ada render visual atau uji tombol WebUI di browser**. Jangan mengulang unduhan yang sama tanpa perubahan jalur/metode.
- Lingkungan exec mempunyai PID namespace sementara tetapi `/proc` host. Uji daemon awal gagal membaca `/proc/$$/cmdline`; **tidak melemahkan pemeriksaan proses dalam modul**. Untuk bukti 39 uji, adapter LD_PRELOAD khusus scratch memetakan pembacaan cmdline ke proses yang sama/namespace yang sama. GitHub Ubuntu normal tidak memerlukan adapter ini.
- Tidak ada akses ke kuota pengguna; checkpoint ini dipicu perintah owner, bukan deteksi kuota otomatis.

### Lokasi sementara bila sesi yang sama masih tersedia

- Workspace: `/workspace/scratch/6dcb3ca95c1c`
- Repo kerja: `/workspace/scratch/6dcb3ca95c1c/Cogan`
- Source sparse: `/workspace/scratch/6dcb3ca95c1c/kernel-compile-check`; build output: `/workspace/scratch/6dcb3ca95c1c/kernel-check-out`
- Dependensi build diekstrak tanpa instalasi sistem: `/workspace/scratch/6dcb3ca95c1c/build-tools-root`; paket .deb di `build-deps`.
- Untuk build lokal: PATH prepend `build-tools-root/usr/bin`; `BISON_PKGDATADIR=.../usr/share/bison`; `M4=.../usr/bin/m4`; HOSTCFLAGS include `.../usr/include`; HOSTLDFLAGS `-L.../usr/lib/x86_64-linux-gnu`.
- Adapter pengujian: `/workspace/scratch/6dcb3ca95c1c/proc-shim.c` / `proc-shim.so`. Hanya dipakai lokal, jangan dimasukkan ke modul/kernel.
- Log: `power-tests-2.log`, `thermal-tests-2.log`, `bridge-tests-2.log`, `kernel-check-config.log`, `kernel-object-check.log`, `browser-download.log`.
- Helper upload terkini sudah dibaca/disiapkan di `library-helpers-current`, tetapi belum ada writeback modul. Tidak perlu membaca ulang lampiran bila checkout kandidat ini ada.

## Berikutnya (hanya setelah owner meminta lanjut)

1. Checkout branch checkpoint, baca dokumen ini dan W63; jangan memulai ulang pekerjaan yang sudah lulus.
2. Tinjau lifecycle QoS, pemulihan saat beralih fallback ↔ bridge, timeout penerapan/stop, pemulihan saklar cas saat interupsi dan lock stale setelah reboot/PID reuse. Penyimpanan metadata terakhir dan hasil readback perlu ditinjau; jangan mengklaim semua angka diterima hanya karena write sukses.
3. Selesaikan compile object pada source target yang tepat. Jika source sementara dipakai lebih dulu, tambahkan subtree include SELinux tanpa `--no-cone`, lalu lanjutkan dari error asli; catat versi/arsitektur bukti. Build penuh ARM64 dan uji HP tetap dibutuhkan.
4. Selesaikan pemeriksaan UI: render mobile, tombol Simpan/Paksa/Reset/Mulai/Henti, penanganan error async, label "ambang suhu" (masih ada "jaga suhu ≤" lama), dan penyelarasan README ID/EN. Cooling device sudah ditampilkan; menghindari rem ganda berdasarkan cooling device **belum** diimplementasikan.
5. Verifikasi hanya yang terpengaruh perubahan terakhir. Jangan mengulang CI hijau tanpa alasan. Satu topik, satu push/PR setelah kandidat layak ditinjau; checkpoint sekarang belum PR.
6. Setelah pemeriksaan layak: kemas dua ZIP satu tingkat dengan `scripts/package_module.py`; uji ZIP; ganti file lampiran yang sama bila tetap diminta (IDs di bawah), jangan membuat duplikat tanpa alasan. Barulah laporkan modul tersedia dan batas kesiapan kernel dengan jelas.
7. Kompilasi kernel lewat Actions hanya owner (A10); rilis/flashing tetap owner. Jangan menganggap uji kernel lama berlaku pada overlay baru.

## Menunggu owner

- Perintah `Lanjutkan` untuk membuka kembali pekerjaan.
- Setelah kode dan kompilasi siap: uji HP dan build kernel oleh owner. Memasang ZIP modul saja tidak membuat kernel lama memiliki bridge.

## Identitas file asal

- `Cogan-Power-Mode-v1.0.zip`: `libfile_230843fe39108191ba8619c6daf68f71`; sumber lokal `upload/Cogan-Power-Mode-v1.0.zip`.
- `Cogan-Thermal-Monitor-v1.0.zip`: `libfile_019a454677b88191acd2ecf5d17960c6`; sumber lokal `upload/Cogan-Thermal-Monitor-v1.0.zip`.

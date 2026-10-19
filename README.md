<div align="center">

# Cogan Kernel

**Kernel GKI 6.1 untuk Android dengan KernelSU, KernelSU Next, BakaSU dan SUSFS**

**🇮🇩 Bahasa Indonesia** · [🇬🇧 English](README.en.md)

[![Lisensi: GPL-3.0](https://img.shields.io/badge/lisensi-GPL--3.0-blue.svg)](LICENSE)
[![GKI android14-6.1](https://img.shields.io/badge/GKI-android14--6.1-3DDC84.svg?logo=android&logoColor=white)](#perangkat-yang-didukung)
[![Rilis](https://img.shields.io/github/v/release/cogan17/Cogan?include_prereleases&filter=v*&label=rilis)](https://github.com/cogan17/Cogan/releases)

[Fitur](#fitur) · [Varian](#varian) · [Unduh & pasang](#unduh--pasang) · [Bootloop?](#bootloop) · [Pakai CMD](#pakai-cmd-platform-tools) · [Build sendiri](#build-sendiri)

</div>

> [!CAUTION]
> Cogan tidak bertanggung jawab atas perangkat yang rusak (*brick*) atau data yang hilang. Dengan mem-flash, Anda menanggung semua risikonya. Cadangkan data dan siapkan `boot.img` stock **sebelum** flash. Lihat **[Panduan Bootloop](docs/bootloop.md)**.

## Tentang

Kernel generik yang dibangun dari sumber GKI 6.1 ([GKI-Duchamp-6.1](https://github.com/ahmed-alnassif/GKI-Duchamp-6.1)) dengan root berbasis kernel dan SUSFS untuk menyembunyikan root. Dibuat agar cocok dengan banyak perangkat GKI `android14-6.1`, tetapi tidak dijamin berjalan di semua perangkat.

## Fitur

- **KernelSU / KernelSU Next / BakaSU**: root berbasis kernel
- **SUSFS**: menyembunyikan root (sus path, sus mount, sus kstat, sus map, spoof uname dan cmdline, open redirect, sembunyikan simbol)
- **NoMount**: metamodul mount, selalu ikut
- **Baseband Guard (BBG)**: melindungi partisi penting dari penulisan tanpa izin (bisa dimatikan)
- **Networking**: TCP BBRv3 (default; terdaftar sebagai `bbr` dan `bbr3`, jadi terdeteksi TCP Optimiser), Westwood+, FQ, IP Set, NAT IPv6 (bisa dimatikan)
- **Performa**: timer 300 Hz, MGLRU, zRAM LZ4 + writeback, mq-deadline, kompresi F2FS, NTSync
- **TMPFS**: xattr dan POSIX ACL
- **Toolchain**: Neutron Clang (versi dikunci) dengan pilihan Full LTO, Thin LTO, atau tanpa LTO
- **Xiaomi 14T Pro (rothko)**: kernel khusus HP ini dikembangkan terpisah di repo **[cogan17/Xiomi-14t-pro](https://github.com/cogan17/Xiomi-14t-pro)** dengan salinan mesin build sendiri (root KSUN / BakaSU + SUSFS, ZIP khusus rothko, gate KMI). Cogan tetap kernel GKI 6.1 umum.
- **Komponen terkunci**: kernel, root manager, SUSFS, NoMount, BBG, AnyKernel3 dan toolchain dipin ke commit tertentu, dan hanya diperbarui lewat **Cogan Manual Update**. KernelSU, KernelSU Next dan NoMount mengikuti **tag rilis resmi**; BakaSU juga dapat memakai snapshot CI resmi setelah pergantian nama. Sumber kernel dan APK manager selalu dikunci bersama

## Perangkat yang didukung

- Perangkat dengan kernel stock **GKI `6.1.x-android14`**. Cek di *Setelan → Tentang ponsel → Spesifikasi lengkap → Versi kernel*.
- Sublevel tersedia **6.1.160 ke atas** (varian SUSFS: **6.1.167 ke atas**); `lts` = sublevel terbaru. Pilih sublevel yang **sama atau lebih baru** dari kernel stock Anda.
- **Xiaomi 14T Pro (rothko)**: pakai build khusus dari [cogan17/Xiomi-14t-pro](https://github.com/cogan17/Xiomi-14t-pro).
- Bootloader harus sudah terbuka.

## Varian

| Pilihan di form | Nama varian (ZIP) | Root | SUSFS | Catatan |
|---|---|---|---|---|
| KernelSU | `KernelSU` | KernelSU | ❌ | |
| KernelSU + SUSFS | `KernelSU+SuSFS` | KernelSU | ✅ | |
| KernelSU Next | `KernelSU-Next` | KernelSU Next | ❌ | |
| KernelSU Next + SUSFS | `KernelSU-Next+SuSFS` | KernelSU Next (fork pershoot) | ✅ | Kernel **6.1.167 ke atas** dari pin Manual Update (`lts` = pin terbaru). None/Thin/Full LTO, BBG dan Networking mengikuti form; tidak perlu data percobaan atau pencatatan tree lama |
| BakaSU + SUSFS | `BakaSU+SuSFS` | BakaSU | ✅ | **Ditahan upstream** pada pin `2489b38582a0`; menunggu pembaruan kompatibilitas SUSFS |
| KSUN + SUSFS & BakaSU + SUSFS | `KernelSU-Next+SuSFS` dan `BakaSU+SuSFS` | Keduanya, ZIP terpisah | ✅ | Dua varian di atas dalam satu run (aturan KSUN + SUSFS berlaku) |
| Vanilla | `Vanilla` | ❌ | ❌ | Tanpa root |
| All variants (advanced) | Semua varian standar + `Vanilla+NoLTO` + `Compat+…` | | | `Compat` tanpa LTO, untuk perangkat yang tidak mau boot dengan varian standar |

## Unduh & pasang

<details>
<summary><b>6 langkah</b>: cek kernel → siapkan <code>boot.img</code> stock → unduh ZIP → flash → pasang manager → reboot</summary>

1. Pastikan kernel stock Anda `6.1.x-android14` dan bootloader sudah terbuka.
2. **Siapkan `boot.img` stock** yang sama persis dengan versi ROM Anda ([caranya](docs/bootloop.md#1-siapkan-bootimg-stock-sebelum-flash)).
3. Unduh ZIP dari **[Releases](https://github.com/cogan17/Cogan/releases)**, lalu cocokkan SHA256-nya dengan `checksums.txt`.
4. Flash ZIP AnyKernel3 dengan aplikasi flasher kernel di perangkat yang sudah root, yaitu [Kernel Flasher](https://github.com/fatalcoder524/KernelFlasher) (versi fatalcoder524), atau lewat custom recovery. ZIP ini **tidak** bisa di-flash lewat `fastboot`; untuk fastboot, buat `.img` dulu ([Pakai CMD](#pakai-cmd-platform-tools)).
5. Pasang APK manager yang versinya sama dengan kernel. APK ini ikut di artifact build, dan tautannya tercantum di catatan rilis (bagian **Versi komponen**, bersama versi kernel, SUSFS, NoMount dan BBG); bisa juga diunduh dari rilis resmi dengan tag yang sama: [KernelSU](https://github.com/tiann/KernelSU/releases), [KernelSU Next](https://github.com/KernelSU-Next/KernelSU-Next/releases) atau [BakaSU](https://github.com/Baka-SU/BakaSU/releases). Modul NoMount (ZIP) dipasang lewat menu Modul di manager.
6. Reboot. Kalau macet di logo atau terus restart, buka **[Panduan Bootloop](docs/bootloop.md)**.

</details>

## Modul tambahan

<details>
<summary><b>Cogan Thermal Monitor</b> · <b>Cogan Power Mode</b> (uji)</summary>

- **[Cogan Thermal Monitor](modules/thermal-monitor/README.md)** (uji): mencatat semua suhu HP beserta penyebabnya (aplikasi, game, cas, proses kernel), membuat ringkasan dan menyimpan log lewat WebUI KernelSU / KernelSU Next / BakaSU. Hanya membaca sensor.
- **[Cogan Power Mode](modules/power-mode/README.md)** (uji): mode Hemat / Seimbang / Game dan auto cut charging. Mode Seimbang menjaga suhu memakai laporan Cogan Thermal Monitor, misalnya menjeda cas bila cas yang membuat panas.

</details>

## Bootloop?

Jangan panik dan **jangan factory reset**. Kenali dulu penyebabnya:

<details>
<summary>Tabel gejala, penyebab, cara pulih dan log</summary>

| Gejala | Penyebab | Pulihkan | Lihat log |
|---|---|---|---|
| Macet atau restart di **logo pertama**, animasi boot tidak muncul | **Kernel** | Flash `boot.img` stock lewat fastboot ([caranya](docs/bootloop.md#2-pulihkan-dari-bootloop)) | Setelah menyala: *Opsi pengembang → Laporan bug* atau `adb bugreport`, cari `LAST KMSG` / `Kernel panic` ([detail](docs/bootloop.md#bootloop-karena-kernel)) |
| **Animasi boot** berulang, atau bootloop setelah memasang modul | Biasanya **modul** | **Safe mode**: saat logo pertama, tekan Volume Bawah lebih dari 3 kali (tekan-lepas), lalu hapus modulnya di manager ([caranya](docs/bootloop.md#kernel-atau-modul)) | Di safe mode: manager → **Pengaturan → Kirim log** ([detail](docs/bootloop.md#bootloop-karena-modul)) |

Kalau safe mode tetap bootloop, anggap penyebabnya kernel. Log kernel (pstore) **tertimpa setelah restart berikutnya**, jadi ambil segera setelah HP menyala. Langkah lengkap, termasuk bagian khusus **Xiaomi 14T Pro (rothko)**, ada di **[Panduan Bootloop](docs/bootloop.md)**.

</details>

## Pakai CMD (Platform Tools)

Semua perintah di bawah dijalankan di **CMD Windows** dari folder Platform Tools. File hasilnya tersimpan di folder yang sama.

<details>
<summary><b>Persiapan</b></summary>

1. Unduh [SDK Platform-Tools untuk Windows](https://developer.android.com/tools/releases/platform-tools), lalu ekstrak, misalnya ke `C:\platform-tools`.
2. Di HP: *Setelan → Tentang ponsel*, ketuk **Versi OS** 7 kali, lalu di *Opsi pengembang* aktifkan **USB debugging**.
3. Buka folder `C:\platform-tools` di File Explorer, ketik `cmd` di kolom alamat, lalu tekan Enter.
4. Hubungkan HP, jalankan `adb devices`, dan izinkan di HP. Status harus `device`.
5. Untuk perintah `su`: buka manager root → **Superuser**, lalu izinkan **Shell**.

</details>

<details>
<summary><b>Ambil log</b></summary>

| Untuk | Perintah |
|---|---|
| Bugreport lengkap, termasuk log kernel dari boot yang gagal (pstore) | `adb bugreport bugreport.zip` |
| Logcat boot sekarang | `adb logcat -b all -d > logcat.txt` |
| Logcat langsung saat animasi boot berulang (USB debugging harus sudah diizinkan sebelumnya) | `adb logcat -b all > logcat-bootloop.txt`, lalu `Ctrl+C` setelah ±1 menit |
| Log kernel sekarang (root) | `adb shell "su -c dmesg" > dmesg.txt` |
| Log kernel boot sebelumnya / pstore (root) | `adb shell "su -c 'cat /sys/fs/pstore/console-ramoops*'" > ramoops.txt` |
| Cek BBRv3 aktif (harus `bbr`) | `adb shell "su -c cat /proc/sys/net/ipv4/tcp_congestion_control"` |
| Cek BBG aktif (harus muncul baris `baseband_guard version: …`; kalau kosong, reboot lalu jalankan segera) | `adb shell "su -c 'dmesg \| grep baseband_guard'"` |
| Cek nama `bbr3` untuk TCP Optimiser | `adb shell "su -c cat /proc/sys/net/ipv4/tcp_available_congestion_control"` |

</details>

<details>
<summary><b>Fastboot: pulihkan atau pasang <code>.img</code></b></summary>

```bat
adb reboot bootloader
fastboot devices
fastboot flash boot boot-stock.img
fastboot reboot
```

`adb reboot bootloader` hanya bisa dipakai saat HP menyala. Saat bootloop, masuk fastboot lewat tombol (Xiaomi: **Volume Bawah + Power**). Ganti `boot-stock.img` dengan `cogan-boot.img` untuk memasang kernel Cogan.

</details>

<details>
<summary><b>Membuat <code>cogan-boot.img</code> (kernel Cogan sebagai <code>.img</code>)</b></summary>

Cogan sengaja **tidak** membagikan `boot.img` generik. Kompresi kernel dan *security patch level* tiap HP berbeda, dan kalau tidak cocok HP bisa bootloop. Peringatan yang sama ada di [panduan resmi KernelSU](https://kernelsu.org/guide/installation.html#patch-boot-image). Cara aman yang dianjurkan KernelSU adalah membungkus kernel Cogan ke dalam `boot.img` stock milik Anda sendiri, sama seperti yang dilakukan ZIP AnyKernel3.

1. Taruh tiga file ini di `C:\platform-tools`:
   - `boot-stock.img`, dengan versi ROM yang sama persis ([caranya](docs/bootloop.md#1-siapkan-bootimg-stock-sebelum-flash)),
   - `Image`, diambil dari dalam ZIP kernel Cogan (`1-KERNEL_…zip`),
   - `libmagiskboot.so` dari APK [Magisk resmi](https://github.com/topjohnwu/Magisk/releases): ganti akhiran `.apk` menjadi `.zip`, lalu ambil `lib/arm64-v8a/libmagiskboot.so`.
2. Saat HP menyala (kernel apa saja, tanpa root), jalankan:

```bat
adb push libmagiskboot.so /data/local/tmp/magiskboot
adb push boot-stock.img /data/local/tmp/
adb push Image /data/local/tmp/
adb shell "cd /data/local/tmp && chmod +x magiskboot && ./magiskboot unpack boot-stock.img && mv -f Image kernel && ./magiskboot repack boot-stock.img cogan-boot.img"
adb pull /data/local/tmp/cogan-boot.img
```

3. Flash lewat fastboot seperti di atas: `fastboot flash boot cogan-boot.img`.

Simpan `cogan-boot.img` yang sudah terbukti boot bersama `boot-stock.img`. Kalau kernel yang lebih baru bermasalah, cukup flash kembali yang lama. Buat ulang setiap kali ROM diperbarui (OTA), karena `boot.img` stock ikut berubah. Jika HP mendukung, `fastboot boot cogan-boot.img` bisa mencoba kernel tanpa mem-flash; banyak HP Xiaomi/MediaTek tidak mendukungnya.

</details>

## Build sendiri

Buka **Actions → Cogan Kernel Builder → Run workflow** di repositori Anda.

<details>
<summary><b>Isian form</b></summary>

| Isian | Keterangan |
|---|---|
| Root Manager | Varian yang dibangun (lihat tabel Varian) |
| Build Mode | `Standard Build` |
| LTO Package | Full LTO (default), Thin LTO, atau tanpa LTO; NoMount selalu ikut |
| Kernel Version | Dikunci `6.1` |
| Build Revision | Opsional, format `r` + angka (mis. `r9`). Dipakai di versi kernel (`6.1.177-Cogan-r9-…`), nama ZIP, banner flasher dan nama rilis; tanpa isian dipakai nomor run. Build ulang di hari yang sama? Naikkan revisinya (`r10`) agar nama rilis tidak bentrok |
| Kernel Sublevel | `lts` = terbaru, atau angka saja (mis. `177`, bukan `6.1.177`); tersedia 6.1.160 ke atas, varian SUSFS 6.1.167 ke atas |
| Build Time | `N` = waktu build asli, atau waktu tetap seperti `Thu Jan 1 00:00:00 UTC 2026` |
| Networking | BBRv3 dan paket jaringan tambahan (default aktif; bisa dimatikan pada semua varian) |
| BBG | Baseband Guard (default aktif) |

</details>

<details>
<summary><b>Hasil build</b>: ZIP kernel, APK manager dan modul NoMount</summary>

Saat run hijau, artifact bernomor bisa langsung diunduh (tidak perlu diekstrak):

| File | Isi | Cara pakai |
|---|---|---|
| `1-KERNEL_Cogan-6.1.x_<varian>_<rilis>.zip` | Kernel (ZIP AnyKernel3) | Flash dengan Kernel Flasher |
| `2-MANAGER_<root manager>_<versi>.apk` | Root manager resmi, commit sumber cocok dengan kernel | Install APK |
| `3-MANAGER-SPOOFED_<root manager>_<versi>.apk` | Manager yang sama dengan nama paket acak, dari commit yang sama; build CI BakaSU disalin ke `cogan-mirror` karena artifact Actions kedaluwarsa | Install **salah satu**: 2 atau 3 |
| `4-NOMOUNT-MODULE_<versi>.zip` | Modul NoMount resmi, versi sama dengan NoMount di kernel | Pasang di manager → Modul |

Artifact `build-…` dan `build-env-…` adalah file internal; abaikan saja. Ringkasan run berisi tabel yang sama beserta SHA256, dan baris **Fitur kernel** (mis. `SUSFS, BBRv3 (default), BBG, NoMount, Full LTO`) yang dibaca dari config hasil build. Baris yang sama muncul di Kernel Flasher saat flash. Semua versi ini dikunci bersama oleh **Cogan Manual Update**. Kalau upstream punya versi yang lebih baru (sublevel kernel GKID 6.1, SUSFS, root manager atau NoMount), ringkasan run menampilkan **🔔 Pengingat**: jalankan Cogan Manual Update (`update` → `kernel-6.1`, `susfs`, `root-managers` atau `nomount`), lalu build ulang. Pengingat SUSFS hanya muncul di varian SUSFS. KSUN + SUSFS mengikuti pin kernel terbaru yang sama dan mendapat pengingat kernel. SUSFS bawaan fork pershoot diperbarui terpisah dari SUSFS generik. Semua kombinasi LTO/BBG/Networking bisa dijalankan tanpa bukti percobaan lama; checksum patch, kompatibilitas source dan konfigurasi hasil build tetap diperiksa pada setiap build. Catatan uji lama disimpan sebagai arsip, bukan syarat membuka fitur.

</details>

<details>
<summary><b>Memperbarui komponen</b></summary>

Buka **Actions → Cogan Manual Update**.
- `check` hanya menampilkan laporan versi.
- `update` menerapkan versi baru ke `dev`. Bila push langsung ditolak aturan branch, dibuat PR otomatis di repo ini yang langsung dicek Validate; merge PR itu setelah Validate hijau. Pembuatan PR perlu *Settings → Actions → General → Allow GitHub Actions to create and approve pull requests*.

Run workflow build hanya meng-compile dan tidak pernah memperbarui komponen sendiri.

</details>

<details>
<summary><b>BakaSU dan status SUSFS</b></summary>

**BakaSU:** rilis `v4.2.0-rc3` masih memakai nama ReSukiSU. Saat rilis terbaru masih mendahului pergantian nama, Manual Update (`update` → `root-managers`) memilih satu run **Build Manager** resmi yang sukses dari `push` ke `main`. Sumber kernel serta APK normal dan spoofed dikunci ke commit yang sama; kedua APK diperiksa label internalnya harus **BakaSU**, lalu disimpan di `cogan-mirror` dengan SHA256. Unduh APK yang disertakan build (nama versi `ci-<commit>`). Bila pasangan APK tidak tersedia atau tidak cocok, pin BakaSU tidak diubah. Kompatibilitas kernel tetap harus lolos kompilasi dan uji seperti biasa.

**Status SUSFS (17 Oktober 2026):** APK pin `2489b38582a0` sudah berlabel BakaSU, tetapi sumber kernelnya [diblok oleh upstream](https://github.com/Baka-SU/BakaSU/commit/48fa4bb7ec8bddb8ea932a8c9be0877f89a1fa73): SUSFS belum mengikuti perubahan KernelSU dan dapat menyebabkan deteksi `selinux_hide`. Build memeriksa guard commit yang dipin sebelum mengunduh kernel/toolchain; Manual Update menolak calon pin yang masih diblok sebelum mengunduh APK atau mengubah pin. Guard tidak dihapus dan snapshot lama tidak dipilih sebagai jalan pintas. Pilih **KernelSU Next + SUSFS** saja selama BakaSU ditahan; pilihan gabungan tetap gagal untuk job BakaSU.

</details>

<details>
<summary><b>Membersihkan riwayat run</b></summary>

Buka **Actions → Hapus log run lama**. Isi `simpan_hari` (default 7), kosongkan konfirmasi untuk cek saja, lalu jalankan lagi dengan `HAPUS`. Run yang masih berjalan, run dalam rentang hari itu, dan run yang dirujuk dokumen atau catatan rilis tidak dihapus.

</details>

## Terima kasih

<details>
<summary>Proyek yang dipakai Cogan</summary>

- **GKID Kernels dan GKI-Duchamp-6.1**: [Ahmed Al-Nassif](https://github.com/ahmed-alnassif) (proyek dasar dan sumber kernel)
- **KernelSU**: [tiann](https://github.com/tiann/KernelSU)
- **KernelSU Next**: [KernelSU-Next](https://github.com/KernelSU-Next/KernelSU-Next)
- **KernelSU Next fork SUSFS**: [pershoot](https://github.com/pershoot/KernelSU-Next)
- **BakaSU**: [Baka-SU](https://github.com/Baka-SU/BakaSU)
- **SUSFS**: [simonpunk](https://gitlab.com/simonpunk/susfs4ksu)
- **NoMount**: [maxsteeel](https://github.com/maxsteeel/nomount)
- **Baseband Guard (BBG)**: [vc-teahouse](https://github.com/vc-teahouse/Baseband-guard)
- **AnyKernel3**: [osm0sis](https://github.com/osm0sis/AnyKernel3) (lewat [AK3-GKID](https://github.com/ahmed-alnassif/AK3-GKID))
- **Neutron Clang**: [Neutron-Toolchains](https://github.com/Neutron-Toolchains/clang-build-catalogue)
- Tampilan README terinspirasi [Wild Kernels](https://github.com/WildKernels/GKI_KernelSU_SUSFS)

</details>

Menemukan bug? Buka [Issue](https://github.com/cogan17/Cogan/issues) dan lampirkan log. Caranya ada di [Panduan Bootloop](docs/bootloop.md#4-setelah-berhasil-boot-ambil-log).

## Lisensi

[GPL-3.0](LICENSE)

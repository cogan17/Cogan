# Integrasi Cogan kernel dan modul

[English](#english)

Power Mode **v1.1.1** dan Thermal Monitor **v1.2.1** tetap dapat dipasang secara terpisah. Pada kernel lama, pembacaan sensor dan kontrol sysfs yang tersedia tetap bekerja. **Pengenalan dua arah dan identitas asli yang terverifikasi memerlukan kernel Cogan baru dengan `CONFIG_COGAN_BRIDGE=y`**. Menginstal ZIP modul tidak menambahkan driver ke kernel yang sedang berjalan.

## Perbaikan WebUI Android (v1.1.1 / v1.2.1)

Power v1.1 dapat mengeluarkan `"controls":,` karena delimiter `/` pada regex daftar kontrol tidak di-escape. `mawk` menerima penulisan lama, tetapi one-true-awk (Android) dan BusyBox menolaknya. v1.1.1 memperbaiki delimiter itu, termasuk ketika berkas hasil kontrol masih kosong. Kedua WebUI kini menampilkan kesalahan baca beserta tombol **Coba lagi**, memeriksa exit code dan tidak menampilkan seluruh respons JSON sebagai toast.

CI memasang mksh, one-true-awk dan BusyBox; pengujian mencakup hasil CPU, daftar kosong/path saklar, serta status/sensor/ringkasan Thermal pada kombinasi shell dan awk yang tersedia. Setelan dan riwayat dipertahankan; pasang ZIP pembaruan lalu reboot sekali.

## Kontrol WebUI

| Tombol | Power Mode | Thermal Monitor |
|---|---|---|
| Simpan | Simpan angka; pengendali yang aktif membaca pada interval berikutnya | Simpan setelan pencatatan |
| Paksa / Terapkan | Simpan, mulai, tunggu hasil penerapan pertama, lalu terapkan ulang tiap interval | Terapkan setelan pencatatan sekarang dan mulai pencatat |
| Henti | Hentikan pengendali, lepas QoS milik Cogan, pulihkan perubahan sysfs milik modul | Hentikan pencatatan dan heartbeat |
| Mulai | Aktif kembali dengan setelan tersimpan | Aktif kembali dengan setelan tersimpan |
| Reset default | Pulihkan kontrol milik modul, kembalikan setelan bawaan, berhenti | Pulihkan setelan bawaan, berhenti; riwayat dan log tetap ada |

Henti dan Reset tetap berhenti setelah reboot sampai Mulai ditekan. Bawaan baru/reset cas **95% / 90%**; upgrade mempertahankan setelan 80/75 atau pilihan lain yang sudah tersimpan. Reset Power Mode juga menghapus hasil deteksi saklar cas, sehingga dapat dicari ulang.

Target suhu adalah **ambang pengendalian**, bukan jaminan suhu fisik. Batas CPU adalah **batas maksimum**, bukan frekuensi tetap. Paksa menerapkan ulang kontrol yang didukung dan membaca kembali hasilnya; tidak menonaktifkan batas termal, memalsukan sensor, mengunci frekuensi, mengaktifkan bypass charging, atau mengatasi penolakan driver/SELinux. Tabel Kontrol kernel membedakan diterima, dibatasi lebih rendah, berubah/ditolak, gagal ditulis dan tidak didukung. Status penerapan adalah hasil pemeriksaan pada waktu sampel, bukan jaminan tidak berubah sesudahnya.

## Identitas asli dan pengenalan dua arah

Bridge built-in menyediakan `/sys/kernel/cogan/` (atribut hanya bisa dibaca/ditulis root). `release` berasal dari **`UTS_RELEASE` saat kompilasi**, `banner` dari **`linux_banner`**, sehingga bukan hasil panggilan uname yang dipengaruhi SUSFS. Kedua modul menampilkan identitas ini berdampingan dengan uname, sumber pembacaan, fitur bawaan, heartbeat kedua modul dan keadaan cooling device.

Tanpa bridge, `/proc/sys/kernel/osrelease` ditampilkan sebagai **kandidat belum terverifikasi**; uname menjadi fallback terakhir. `/proc` juga dapat diubah oleh patch/konfigurasi lain, sehingga perbedaan terhadap uname tidak dianggap bukti mutlak identitas asli. Bridge ABI selain 1 tidak diklaim kompatibel.

Modul yang aktif memperbarui `power_client` atau `thermal_client`; kernel mencatat versionCode dan usia heartbeat. Angka 0 berarti berhenti, atau heartbeat sudah kedaluwarsa (900 detik). Ini pendaftaran klien root, bukan verifikasi tanda tangan APK/modul. Kedua modul juga membaca pemasangan, versi dan proses pasangannya. Power tidak menambah langkah pengereman ketika cooling device CPU native aktif dan suhu sudah datar/turun; bila suhu terus naik, ambang modul tetap berlaku. Thermal tetap menyediakan `run/latest`; Power tetap mencatat `modes.tsv` untuk ringkasan per mode.

## ABI 1

| Atribut | Akses | Isi |
|---|---|---|
| `abi` | 0400 | `1` |
| `release`, `banner` | 0400 | Identitas build yang tidak mengambil hasil uname |
| `features` | 0400 | Dukungan bridge, CPU QoS, SUSFS, NoMount, BBG yang dikompilasi |
| `power_client`, `thermal_client` | 0600 | Tulis versionCode (0 unregister); baca `versionCode age_seconds` |
| `limits` | 0600 | Tulis `big_pct little_pct ttl_seconds`; `0 0 0` melepas permintaan |
| `limits` (baca) | 0600 | `big_pct little_pct remaining_seconds policy_count last_error` |
| `policies` | 0400 | Tiap baris: CPU pengelola, batas permintaan Cogan (kHz), batas gabungan QoS (kHz) |

Persentase 20–100, lease 5–180 detik; modul memakai 3× interval (minimal 30 detik). CPU minimum hardware tetap dipatuhi. Driver menambah permintaan **FREQ_QOS_MAX tersendiri**, sehingga batas termal/vendor yang lebih rendah tetap membatasi. Kebijakan CPU yang dibuat/dihapus (hotplug/driver) ditangani notifier CPUFreq. Kernel melepas permintaan setelah lease habis bila modul tidak memperbarui; pemeriksaan memakai delayed work deferrable, sehingga tidak membangunkan CPU idle hanya untuk pemeriksaan ini. Berhenti normal melepasnya langsung. Perlindungan lease ini khusus batas CPU, bukan saklar cas/uclamp.

Pada kernel lama, modul menyimpan nilai sysfs sebelum perubahan, mempertahankan batas eksternal yang lebih rendah dan hanya mengembalikan node yang masih cocok dengan perubahan miliknya. Perubahan dari dua penulis pada node sysfs yang sama tidak bisa dipisahkan sempurna; status readback membantu melihat konflik. Saklar cas tetap bergantung pada driver perangkat dan perlu lolos uji berhenti serta lanjut. Driver charger GKI generik tidak dapat menjamin setiap hardware mendukung auto cut.

## Build dan pengujian

`build.sh` memasang overlay aditif melalui `scripts/install_cogan_bridge.py` **setelah** replay sumber terkunci berhasil, sebelum defconfig. Bridge adalah built-in (`bool`), tanpa LKM. Tidak mengubah struktur vendor/KMI, pin/manifest kandidat, atau pengaman BakaSU/SUSFS. Build gagal bila `CONFIG_COGAN_BRIDGE=y` tidak terpilih. Perubahan ini menambah kode kernel sehingga bukti boot kernel sebelumnya tidak membuktikan build baru aman.

1. Pasang kedua ZIP pembaruan lewat root manager, lalu reboot sekali agar skrip versi lama berhenti.
2. Pada kernel lama, periksa pembacaan sensor, Simpan/Paksa/Henti/Reset dan tabel hasil kontrol.
3. Owner menjalankan build kernel dari perubahan ini; jangan mengulang run kernel hijau yang tidak memuat perubahan.
4. Setelah kompilasi dan kompatibilitas lulus, owner dapat menguji kernel baru. Periksa kedua klien terdaftar, identitas asli vs uname dan backend `kernel_qos` pada WebUI.
5. Uji Henti: lease Cogan dilepas; batas vendor tetap berlaku. Cabut/pasang charger dan periksa status nyata untuk auto cut. Reset harus mengembalikan setelan, berhenti dan mempertahankan log Thermal.

Tidak ada build GitHub, release publik atau flashing yang dijalankan oleh pembaruan modul ini.

## Bukti verifikasi kandidat

- 47 uji modul lulus (Power 12, Thermal 13, integrasi 19, matriks Android 3); lima uji draft rilis terpisah. Matriks memeriksa mksh/dash/BusyBox ash × one-true-awk/mawk/BusyBox awk.
- Kedua WebUI diuji di browser pada lebar 360 px dengan skrip modul sebenarnya dan sysfs/proc simulasi: Simpan, Terapkan, Mulai/Henti, Reset, penolakan angka tidak valid, dan riwayat Thermal.
- Object bridge **ARM64** berhasil dikompilasi pada pin GKI **6.1.177 `8c24bbff`**, `gki_defconfig`, GCC 13.3; pemeriksaan API native juga lulus. [Bukti terstruktur](validation/cogan-companion-bridge-validation.json).
- Ini belum merupakan build penuh kernel produksi Clang/FullLTO dan belum uji HP. ZIP modul siap untuk pengujian; pengenalan kernel dua arah memerlukan build baru yang memuat bridge.

## English

Power Mode v1.1.1 and Thermal Monitor v1.2.1 use built-in Cogan Bridge ABI 1 when available, and retain verified sysfs fallback on older kernels. Installing module ZIPs does not install a kernel driver: original identity and two-way kernel registration require a newly built kernel.

The v1.1.1 Power fix escapes an awk regex delimiter that Android and BusyBox reject; mawk had accepted it. Both updated WebUIs report command/JSON failures with a persistent Retry panel. CI explicitly installs Android-like shell/awk tools and checks actual module JSON responses.

The bridge exports compile-time `UTS_RELEASE` and `linux_banner`, root-only client heartbeats, and an independent leased CPUFreq MAX QoS request. Thermal/vendor constraints retain precedence. Expiry releases Cogan's CPU request; it does not control charging or uclamp. Native sysfs nodes still implement device-specific charging and game boost. CPU settings are upper bounds; temperature values are policy thresholds, not promises of a fixed physical temperature.

Save persists settings, Apply/Force applies immediately and enables periodic retry in Power Mode, Stop releases/restores owned changes, Start resumes, and Reset restores defaults while leaving the controller stopped. Stops survive reboot. New/reset charging defaults are 95/90; existing settings survive upgrades. Thermal reset keeps history and exported logs. Without the bridge, proc/uname identity remains explicitly unverified. Readback results can report unsupported, failed or conflicting controls instead of claiming success.

The additive build overlay preserves locked replay checks, existing production guards and vendor structure layouts. Full target compilation and device validation are still required before considering the new kernel ready. The owner runs kernel Actions builds, publishes releases and flashes devices.

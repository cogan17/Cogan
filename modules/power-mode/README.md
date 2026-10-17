# Cogan Power Mode

[English](README.en.md)

Modul KernelSU / KernelSU Next / BakaSU (juga Magisk, tanpa WebUI) dengan tiga mode dan auto cut charging. Modul ini melengkapi **[Cogan Thermal Monitor](../thermal-monitor/README.md)**: monitor mencatat suhu dan penyebabnya, Power Mode memakai laporan itu untuk menjaga suhu.

**v1.1:** [integrasi kernel, identitas asli, Simpan/Paksa/Henti/Reset](../../docs/cogan-companion-bridge.md). Reset memakai cas 95/90, menghentikan pengendali, dan tidak menghapus riwayat Thermal. Setelan lama tetap dipertahankan saat upgrade.

## Mode

| Mode | Yang dilakukan |
|---|---|
| 🌿 **Hemat** | CPU besar maksimal 60 % (bisa diatur), ambang kendali 39 °C (target Seimbang − 3) |
| ⚖️ **Seimbang** (bawaan) | Ambang pengendalian suhu 42 °C (bisa diatur) |
| 🎮 **Game** | Performa penuh + boost aplikasi di layar (uclamp); rem darurat baru aktif di 48 °C |

Cara menjaga suhu (tiap 10 detik):

- Terlalu panas → kecepatan maksimal CPU turun 10 % per langkah, sampai paling rendah 40 %.
- Turun minimal 2 °C di bawah batas → kecepatan dikembalikan bertahap.
- Inti kecil selalu dibatasi lebih ringan (+20 %), jadi HP tetap lancar.

## Terhubung dengan Cogan Thermal Monitor

- Monitor menulis laporan singkat tiap sampel: suhu, aplikasi dan **penyebab panas**.
- **Seimbang** memakai penyebab itu:
  - Bila panasnya karena **cas**, cas dijeda dulu sampai suhu turun 3 °C, dan CPU tidak dibatasi.
  - CPU baru ikut dibatasi bila suhu masih naik.
  - Penyebab lain (game, aplikasi berat, latar belakang) ditangani dengan membatasi CPU.
- Power Mode memberi tahu monitor mode mana yang aktif, jadi ringkasan monitor punya bagian **⚡ Per mode** (suhu rata-rata, tertinggi dan waktu panas tiap mode).
- Tanpa monitor, Power Mode tetap jalan dengan sensor sendiri. Penyebab "cas" lalu ditebak dari arus cas ≥ 1500 mA.

## Auto cut charging

- **Berhenti** di 95 %, **lanjut** di 90 % (bisa diatur; berhenti 100 % = tidak pernah).
- **Jeda saat baterai panas**: ≥ 42 °C, lanjut setelah turun 3 °C.
- **Seimbang**: cas juga dijeda bila monitor melaporkan cas sebagai penyebab panas (bisa dimatikan).
- **Pengaman**:
  - baterai ≤ 15 % selalu dicas;
  - Henti memulihkan saklar yang sebelumnya diubah modul; saklar yang dijeda pengendali lain tidak dinyalakan paksa.
- **Saklar cas** dicari otomatis saat pertama dibutuhkan, atau lewat tombol 🔍 **Cari saklar cas** di WebUI (charger harus tercolok). Modul mencoba saklar yang umum di Xiaomi/Qualcomm/MediaTek/Samsung/OnePlus/Motorola. Saklar dipakai hanya bila cas benar-benar berhenti lalu jalan lagi.

## WebUI dan Action

- **WebUI**:
  - pilih mode;
  - lihat suhu, batas CPU per cluster, penyebab panas, baterai dan status cas;
  - atur semua angka;
  - cari saklar cas;
  - log aktivitas ("CPU dibatasi 80 %", "cas dijeda", …).
- **Action**: ganti ke mode berikutnya (Hemat → Seimbang → Game).
- **Hentikan / nonaktifkan modul**: melepas batas QoS Cogan dan memulihkan perubahan sysfs milik modul.

## Catatan

- Batas CPU memakai QoS kernel melalui bridge bila tersedia, atau `scaling_max_freq` pada kernel lama, boost `top-app` (`cpu.uclamp.min`) dan saklar cas. Semuanya dikembalikan saat berhenti. Governor, GPU dan setelan lain tidak disentuh.
- Jangan dipakai bersamaan dengan modul lain yang juga mengatur CPU atau cas (misalnya ACC atau modul performa), karena keduanya akan saling menimpa.

## Untuk pengembang

- Draft rilis: setiap perubahan modul di `dev` otomatis menjadi draft di Releases lewat workflow **Draft modul** (tag `<folder>-vX.Y`), lalu dipublikasikan oleh owner.
- Buat ZIP: `python3 scripts/package_module.py modules/power-mode out/`
- Uji offline (sysfs palsu): `python3 -m unittest tests/test_power_mode.py`
- Skrip:
  - `controller.sh`: pengatur;
  - `report.sh`: dipakai WebUI/Action;
  - `common.sh`: setelan, sensor, CPU, saklar cas;
  - `power.awk`: suhu prosesor, cara baca sama dengan monitor.

# Kernel Xiaomi 14T Pro (rothko)

**🇮🇩 Bahasa Indonesia** · [🇬🇧 English](rothko.en.md)

Build Cogan khusus **Xiaomi 14T Pro** (`rothko`, MediaTek Dimensity 9300+ / MT6989). Isinya kernel GKI 6.1 Cogan yang sama dengan varian lain, tetapi dibatasi dan diberi pengaman untuk HP ini.

> [!CAUTION]
> Siapkan `boot.img` stock yang **sama persis** dengan versi HyperOS Anda sebelum flash. Langkah pemulihan ada di **[Panduan Bootloop → Khusus Xiaomi 14T Pro](bootloop.md#3-khusus-xiaomi-14t-pro-rothko)**.

---

## Isi build rothko

| | |
|---|---|
| Root manager | **KernelSU Next + SUSFS**, **BakaSU + SUSFS**, atau **keduanya** dalam satu run (ZIP terpisah) |
| Fitur | SUSFS, NoMount, Baseband Guard (BBG), BBRv3 (`bbr` dan `bbr3`) + paket jaringan, LTO pilihan (KSUN + SUSFS: Full LTO) |
| Kernel | 6.1, sublevel bisa dipilih: 160–177 untuk BakaSU + SUSFS, **167–177** untuk KSUN + SUSFS; `lts` = terbaru |
| Nama | `Cogan-Rothko` di versi kernel (mis. `6.1.177-Cogan-Rothko-r4-…`), nama ZIP, banner flasher dan nama rilis |
| Pengaman | ZIP AnyKernel3 memakai cek perangkat (`do.devicecheck=1`, `device.name1=rothko`): di HP lain proses flash berhenti dengan *Unsupported device* sebelum `boot` disentuh |
| Revisi & waktu | **Build Revision** (`r` + angka) dan **Build Time** sama seperti varian lain |

---

## Cara build

**Actions → Cogan Kernel Builder → Run workflow**, lalu isi:

| Isian | Pilihan untuk rothko |
|---|---|
| Perangkat | `Xiaomi 14T Pro (rothko)` |
| Root Manager | `KernelSU Next + SUSFS`, `BakaSU + SUSFS`, atau `KSUN + SUSFS & BakaSU + SUSFS` |
| LTO Package | `fullLTO + NoMount + Clean LTO` (wajib untuk KSUN + SUSFS) |
| Kernel Sublevel | `lts`, atau angka 167–177 (BakaSU + SUSFS: 160–177). Pilih yang **sama atau lebih baru** dari kernel stock (`6.1.138` di HyperOS `OS3.0.301.0`) |
| Build Revision | mis. `r4` |
| Build Time | `N` atau waktu tetap |
| Networking, BBG | biarkan aktif (KSUN + SUSFS selalu aktif) |

Pilihan root lain (KernelSU, Vanilla, All variants) ditolak di langkah validasi sebelum kompilasi.

---

## Kenapa dari GKI, bukan dari sumber kernel Xiaomi?

HP GKI seperti rothko memisahkan kernel dan driver: partisi `boot` hanya berisi kernel generik Android (GKI), sedangkan driver MediaTek/Xiaomi ada di modul `vendor_dlkm` yang dimuat lewat antarmuka stabil (KMI `android14-6.1`). Jadi "kernel khusus rothko" adalah kernel GKI yang cocok dengan KMI HP ini.

| | Sumber BSP Xiaomi (`cogan17/Xiomi-14t-pro`) | GKI Cogan (GKID 6.1) |
|---|---|---|
| Versi | `6.1.57`, **lebih tua** dari kernel stock HP (`6.1.138-android14-11`) | `6.1.160`–`6.1.177`, sama atau lebih baru dari stock |
| Sublevel | Tetap | Bisa dipilih |
| Root + SUSFS | Belum pernah terkompilasi (kompilasi PR #8 gagal) | KSUN + SUSFS dan BakaSU + SUSFS **sudah boot di rothko** (uji HP owner 2026-10-16) |

Karena itu build rothko memakai jalur GKI Cogan. Sumber BSP tetap berguna sebagai referensi (mis. untuk membandingkan konfigurasi vendor), tetapi tidak dipakai untuk build.

---

## Sublevel KernelSU Next + SUSFS

KSUN + SUSFS dibangun dari kandidat yang sudah diuji di HP. Patch-nya diterapkan tanpa *fuzz*, dan tiap sublevel punya tree hasil yang dikunci di `configs/ksun-susfs-6.1-features.lock.json` → `sublevels`. Build berhenti bila tree berbeda.

- **167–177**: terverifikasi. 177 tetap identik byte-per-byte dengan build yang lolos uji HP.
- **160–166**: tidak tersedia. Konteks `fs/namespace.c` di sana belum punya hook vendor `do_new_mount_fc` (baru ada di 6.1.167), jadi patch SUSFS tidak cocok tanpa diubah.

Menambah sublevel baru setelah **Cogan Manual Update** memasang pin-nya:

```sh
git init -q /tmp/gkid && git -C /tmp/gkid fetch --depth=1 https://github.com/ahmed-alnassif/GKI-Duchamp-6.1 <commit>
python3 scripts/ksun_susfs_sublevel.py record /tmp/gkid <commit>
```

Salin JSON hasilnya ke `sublevels` di lock, lalu build dan uji di HP. Bila patch tidak cocok, alat ini berhenti dan sublevel itu tetap tidak tersedia.

---

## Flash dan pulihkan

1. Flash `1-KERNEL_Cogan-Rothko-…zip` dengan [Kernel Flasher](https://github.com/fatalcoder524/KernelFlasher) (fatalcoder524). Yang diubah hanya partisi `boot`.
2. Pasang APK manager dari artifact/rilis yang sama (2 **atau** 3) dan modul NoMount (4).
3. Bootloop: flash `boot.img` stock lewat fastboot, lihat [Panduan Bootloop](bootloop.md#3-khusus-xiaomi-14t-pro-rothko).

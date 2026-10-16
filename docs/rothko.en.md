# Xiaomi 14T Pro (rothko) kernel

[🇮🇩 Bahasa Indonesia](rothko.md) · **🇬🇧 English**

A dedicated Cogan build for the **Xiaomi 14T Pro** (`rothko`, MediaTek Dimensity 9300+ / MT6989). It is the same Cogan GKI 6.1 kernel as the other variants, restricted and guarded for this phone.

> [!CAUTION]
> Keep a stock `boot.img` from **exactly** your HyperOS version before flashing. Recovery steps are in the **[Bootloop guide → Xiaomi 14T Pro](bootloop.en.md#3-xiaomi-14t-pro-rothko)**.

---

## What the rothko build contains

| | |
|---|---|
| Root manager | **KernelSU Next + SUSFS**, **BakaSU + SUSFS**, or **both** in one run (separate ZIPs) |
| Features | SUSFS, NoMount, Baseband Guard (BBG), BBRv3 (`bbr` and `bbr3`) + extra networking, selectable LTO (KSUN + SUSFS: Full LTO) |
| Kernel | 6.1 with a selectable sublevel: 160–177 for BakaSU + SUSFS, **167–177** for KSUN + SUSFS; `lts` = latest |
| Name | `Cogan-Rothko` in the kernel version (e.g. `6.1.177-Cogan-Rothko-r4-…`), ZIP name, flasher banner and release name |
| Guard | The AnyKernel3 ZIP checks the device (`do.devicecheck=1`, `device.name1=rothko`): on any other phone flashing stops with *Unsupported device* before `boot` is touched |
| Revision & time | **Build Revision** (`r` + digits) and **Build Time** work as for the other variants |

---

## How to build

**Actions → Cogan Kernel Builder → Run workflow**, then:

| Field | Choice for rothko |
|---|---|
| Device | `Xiaomi 14T Pro (rothko)` |
| Root Manager | `KernelSU Next + SUSFS`, `BakaSU + SUSFS`, or `KSUN + SUSFS & BakaSU + SUSFS` |
| LTO Package | `fullLTO + NoMount + Clean LTO` (required for KSUN + SUSFS) |
| Kernel Sublevel | `lts`, or a number 167–177 (BakaSU + SUSFS: 160–177). Pick the **same or a newer** sublevel than the stock kernel (`6.1.138` on HyperOS `OS3.0.301.0`) |
| Build Revision | e.g. `r4` |
| Build Time | `N` or a fixed time |
| Networking, BBG | keep enabled (always on for KSUN + SUSFS) |

Other root choices (KernelSU, Vanilla, All variants) are refused during validation, before any compilation.

---

## Why GKI and not Xiaomi's kernel source?

GKI phones such as rothko split the kernel from the drivers: the `boot` partition holds only the generic Android kernel (GKI), while the MediaTek/Xiaomi drivers are `vendor_dlkm` modules loaded through a stable interface (KMI `android14-6.1`). A "rothko kernel" is therefore a GKI kernel that matches this phone's KMI.

| | Xiaomi BSP source (`cogan17/Xiomi-14t-pro`) | Cogan GKI (GKID 6.1) |
|---|---|---|
| Version | `6.1.57`, **older** than the phone's stock kernel (`6.1.138-android14-11`) | `6.1.160`–`6.1.177`, same as or newer than stock |
| Sublevel | Fixed | Selectable |
| Root + SUSFS | Never compiled (the PR #8 compile failed) | KSUN + SUSFS and BakaSU + SUSFS **boot on rothko** (owner device test, 2026-10-16) |

So the rothko build uses the Cogan GKI pipeline. The BSP source remains a reference (for example to compare vendor configuration) but is not built.

---

## KernelSU Next + SUSFS sublevels

KSUN + SUSFS is built from the device-tested candidate. Its patches apply without fuzz, and every sublevel has its resulting trees locked in `configs/ksun-susfs-6.1-features.lock.json` → `sublevels`. The build stops if a tree differs.

- **167–177**: verified. 177 stays byte-identical to the build that passed the device test.
- **160–166**: unavailable. Their `fs/namespace.c` lacks the `do_new_mount_fc` vendor hook (added in 6.1.167), so the SUSFS patch does not fit without changes.

Adding a new sublevel after **Cogan Manual Update** has pinned it:

```sh
git init -q /tmp/gkid && git -C /tmp/gkid fetch --depth=1 https://github.com/ahmed-alnassif/GKI-Duchamp-6.1 <commit>
python3 scripts/ksun_susfs_sublevel.py record /tmp/gkid <commit>
```

Copy the printed JSON into `sublevels` in the lock, then build and test on the phone. If the patches do not fit, the tool stops and the sublevel stays unavailable.

---

## Flash and recover

1. Flash `1-KERNEL_Cogan-Rothko-…zip` with [Kernel Flasher](https://github.com/fatalcoder524/KernelFlasher) (fatalcoder524). Only the `boot` partition changes.
2. Install the manager APK from the same artifact/release (2 **or** 3) and the NoMount module (4).
3. Bootloop: flash the stock `boot.img` with fastboot, see the [Bootloop guide](bootloop.en.md#3-xiaomi-14t-pro-rothko).

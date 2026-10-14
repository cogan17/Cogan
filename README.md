# GKID Kernel

<p align="center">
  <img src="docs/banner.png" alt="GKID Kernels Banner">
</p>

[![Build Status](https://github.com/cogan17/Cogan/actions/workflows/build.yml/badge.svg)](https://github.com/cogan17/Cogan/actions/workflows/build.yml)
[![Latest Release](https://img.shields.io/github/v/release/cogan17/Cogan?label=Latest%20Release&color=00aa00)](https://github.com/cogan17/Cogan/releases)
[![Downloads](https://img.shields.io/github/downloads/cogan17/Cogan/total?label=Downloads&color=00aa00)](https://github.com/cogan17/Cogan/releases)
[![Group](https://img.shields.io/badge/Telegram-Group-blue.svg?logo=telegram)](https://t.me/ahmed_alnassif_tg)
[![GitHub License](https://img.shields.io/github/license/cogan17/Cogan?logo=gnu)](/LICENSE)
[![SuSFS](https://img.shields.io/badge/SuSFS-4CAF50?&logo=gitlab&logoColor=white)](https://gitlab.com/simonpunk/susfs4ksu)
[![KernelSU](https://img.shields.io/badge/KernelSU-000000?&logo=github&logoColor=white)](https://github.com/tiann/KernelSU)
[![KernelSU Next](https://img.shields.io/badge/KernelSU--Next-1976D2?&logo=github&logoColor=white)](https://github.com/KernelSU-Next/KernelSU-Next)
[![ReSukiSU](https://img.shields.io/badge/ReSukiSU-E91E63?&logo=github&logoColor=white)](https://github.com/ReSukiSU/ReSukiSU)


**GKI kernel build project for Android** with KernelSU, SuSFS, performance optimizations, battery improvements, and advanced security features.

---

> [!Important]
> - This is a **GKI** kernel, not a custom kernel. Compatibility depends on the device's GKI version, KMI, vendor modules, and successful device testing.
> - Supported GKI versions: **5.10, 5.15, 6.1, 6.6, 6.12** (see [Supported GKI Kernel Versions](#-supported-gki-kernel-versions) below).

---

## Project credits

This repository is a fork-based development project. Credit for upstream GKID work belongs to [Ahmed Al-Nassif](https://github.com/ahmed-alnassif/GKID-Kernels) and to the respective upstream contributors. Any upstream support or donation information should be consulted on the original project page; this fork does not claim ownership of upstream donation details.

---

## ✨ ReSuSFS 

**[ReSuSFS](https://github.com/ahmed-alnassif/ReSuSFS)** – Root hiding made simple, powerful when you need it. A [KernelSU](https://kernelsu.org) module and WebUI that turns SuSFS into clean config files and toggle switches for everyday use, with **strong hiding applied out of the box** via built-in spoofing and hiding scripts for one-tap protection, plus a script manager for power users who want more, all without leaving the WebUI.

---

> [!WARNING]
> **Development status:** This fork is under active construction. The workflow changes in PR #27 are not yet validated by a full kernel build or device boot test. Do not assume that a selected kernel sublevel or variant is flash-ready.
>
> **Scope:** NetHunter, WirelessKSU, and NTSync have been removed from the build path. Standard Android Wi-Fi support is not intentionally removed. DroidSpaces is optional and disabled by default; NoMount remains available.

## ⚡ Quick Start

1. **Check** your kernel version in Settings → About Phone
2. **Download** matching variant from [Releases](https://github.com/cogan17/Cogan/releases)
3. **Flash** using KernelSU app or custom recovery
4. **Manage** SuSFS with [ReSuSFS](https://github.com/ahmed-alnassif/ReSuSFS)

---

## 📱 Supported GKI Kernel Versions

| Linux | Android |
|-------|---------|
| 5.10  | 12      |
| 5.15  | 13      |
| 6.1   | 14      |
| 6.6   | 15      |
| 6.12  | 16      |

---

## ⚙️ Workflow options (PR #27)

The workflow form is defined by the **selected branch**. Until PR #27 is merged, select `feat/optional-sublevel-disable-droidspaces` to view these development inputs; the `dev` branch may show an older form.

- **KERNEL_VERSION:** Choose a GKI line (5.10, 5.15, 6.1, 6.6, or 6.12).
- **KERNEL_SUBLEVEL:** For **6.1 only**, choose `Auto` or an exact value from **161–177**. This is a *version check*, not an automatic source downloader for each sublevel.
- **KERNEL_SOURCE_REF:** For an older 6.1 sublevel, provide a **verified** branch or tag containing the matching kernel source. Without a matching source, the workflow intentionally refuses the build.
- **BUILD_TIME:** `N` (default) uses the runner's current UTC time; alternatively enter a UTC timestamp such as `Sat Oct 10 19:10:00 UTC 2026`. This changes the kernel build timestamp, **not** the Linux version or source commit.
- **EXTRA_FEATURES:** Comma-separated `nomount,clean-lto-cache` (both enabled by default). Remove a name to disable that option; leave blank to disable both.
- **DROIDSPACES:** Optional, disabled by default.

> [!NOTE]
> The 161–177 range describes accepted input values, **not** confirmed availability of a matching source branch for every value. Workflow and device-level validation are still pending; do not treat a selectable option as a tested kernel release.

---

## 🔧 Build Variants

| Variant | Root | SuSFS | LTO | Compat |
|---------|------|-------|-----|--------|
| Vanilla | ❌ | ❌ | Full | ❌ |
| Vanilla+NoLTO | ❌ | ❌ | None | ❌ |
| KernelSU | ✅ | ❌ | Full | ❌ |
| KernelSU+SuSFS | ✅ | ✅ | Full | ❌ |
| KSU+SuSFS+MM | ✅ | ✅ | Full | ❌ |
| KernelSU-Next | ✅ | ❌ | Full | ❌ |
| KSU-Next+SuSFS | ✅ | ✅ | Full | ❌ |
| ReSukiSU+SuSFS | ✅ | ✅ | Full | ❌ |
| Compat+KSU+SuSFS | ✅ | ✅ | Full | ✅ |
| Compat+KSU-Next+SuSFS | ✅ | ✅ | Full | ✅ |
| Compat+LTO+KSU-Next+SuSFS | ✅ | ✅ | Full | ✅ |

**Optional features** (availability depends on the selected variant):
- 🐳 DroidSpaces - Linux userspace support
- 🥷 NoMount - NoMount integration

---

## Performance

| Feature | Description |
|---------|-------------|
| **300Hz Timer** | Reduced input latency for snappier UI response |
| **MGLRU** | Multi-generational LRU for smoother multitasking |
| **zRAM** | LZ4 compression with writeback for memory efficiency |
| **CPU Governors** | schedutil + ondemand for smart power scaling |
| **I/O Scheduler** | mq-deadline optimized for UFS 4.0 storage |
| **F2FS Tuning** | 50ms GC sleep for buttery smooth I/O |
| **Memory Optimizations** | 50% faster memcpy/memset/memcmp operations |
| **ext4 Tuning** | Extended commit age reducing unnecessary writes |

**What this means for you:**
- Apps launch faster
- UI feels more responsive
- Gaming has less stutter
- Multitasking is smoother
- Better framerates in games

---

## 🔋 Battery Life

| Feature | Description |
|---------|-------------|
| **Wakelock Cap** | 500ms cap prevents excessive battery drain |
| **Freeze Timeout** | 20s → 1s for faster deadlock detection |
| **F2FS Optimization** | Reduced GC overhead saves CPU cycles |
| **Alarm Wakeups** | Minimized to reduce standby battery drain |
| **ext4 Commit Age** | 30s commit age reduces write operations |
| **Power Management** | Improved suspend/resume for better idle drain |

**What this means for you:**
- Better standby time
- Less battery drain during use
- Overnight battery lasts longer
- Gaming doesn't kill battery as fast
- All-day battery life

---

## 🌐 Networking

| Feature | Description |
|---------|-------------|
| **TCP BBRv3** | Default congestion control for maximum speed |
| **Westwood+** | Alternative congestion control for WiFi |
| **FQ CoDel** | Fair queuing with controlled delay |
| **IP Set** | Efficient IP/network address management |
| **IPv4/IPv6 NAT** | Full NAT support for tethering |
| **IPsec/ESP** | VPN and secure tunneling support |
| **Netfilter** | Advanced firewall and packet filtering |

**What this means for you:**
- Faster WiFi and mobile data
- Better VPN performance
- Improved tethering speeds
- Lower gaming latency
- Smoother streaming

---

## 🛡️ Security

| Feature | Description |
|---------|-------------|
| **SuSFS** | Advanced filesystem and process hiding |
| **Baseband Guard** | Blocks unauthorized partition writes |
| **Kernel LSM** | SELinux + Baseband Guard integration |
| **Symbol Hiding** | Kernel symbol protection from detection |
| **uname Spoofing** | System information hiding |
| **Open Redirect** | Protected file operations |
| **SUS MAP/PATH/MOUNT** | Complete filesystem hiding |

**What this means for you:**
- Stronger root hiding
- Better banking app compatibility
- Improved security against detection
- Safe from unauthorized system modifications

---

## 🔑 Root Management

| Feature | Description |
|---------|-------------|
| **KernelSU** | Stable kernel-based root with excellent hiding |
| **KernelSU-Next** | Community fork with bleeding-edge features |
| **ReSukiSU** | ReSukiSU kernel integration |
| **Multiple Managers** | Run multiple KernelSU managers simultaneously |
| **Vanilla** | No root for banking and corporate apps |

**What this means for you:**
- Reliable root access
- Apps don't detect root
- Pass SafetyNet/Play Integrity
- Choose your root implementation

---

## 🐳 DroidSpaces

Complete Linux userspace support:
- System V IPC and POSIX message queues
- IPC and PID namespaces
- devtmpfs with xattrs
- POSIX ACLs
- Netfilter and IP Set
- UFW and Fail2ban requirements

**What this means for you:**
- Run Linux apps on Android
- Better container support
- Chroot and proot work better

---

## 🔥 LTO Options

| Option | Description | Best For |
|--------|-------------|----------|
| **FullLTO** | Maximum performance, slower build | Gaming, performance |
| **ThinLTO** | Faster build, good performance | Balanced |
| **NoLTO** | Build compatibility | Problem devices |

---

## 🔄 Compatibility

**Use Compat if:**
- You experience boot issues
- Vendor modules fail to load
- Device KMI mismatch
- Standard variants don't boot

---

## 📥 Downloads

**All releases:** [GitHub Releases](https://github.com/cogan17/Cogan/releases)

**Successful kernel releases may include:**
- 📦 AnyKernel3 flashable packages
- 🔐 SHA256 and MD5 checksums
- 📝 Build information and changelogs

---

## 📡 TCP Congestion Control

Switch congestion control algorithms (temporary, resets on reboot):

```bash
# Westwood+ - better for WiFi and mobile data
su -c "sysctl -w net.ipv4.tcp_congestion_control=westwood"

# BBRv3 - default, best for speed
su -c "sysctl -w net.ipv4.tcp_congestion_control=bbr"
```

**Make permanent:** Create a script in `/data/adb/service.d/` with the sysctl command or use ReSuSFS.

---

## Other Ways to Help

- **Star the Repository** ⭐ - Helps others discover this project
- **Share** 📢 - Spread the word in your community or forums
- **Report Issues** 🐛 - Found a bug? Open an issue with detailed logs
- **Contribute** 🔧 - Pull requests, suggestions, and feedback are always welcome

---

## 💬 Community

- **Discussions:** [GitHub Discussions](https://github.com/cogan17/Cogan/discussions)
- **Issues:** [GitHub Issues](https://github.com/cogan17/Cogan/issues)

---

## 📄 License

See [LICENSE](LICENSE).
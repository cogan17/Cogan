#!/usr/bin/env python3
"""Install the additive built-in bridge after locked source replay, before defconfig."""
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KCONFIG = '''
# Cogan companion ABI (built-in only)
config COGAN_BRIDGE
\tbool "Cogan companion bridge"
\tdepends on CPU_FREQ
\tdefault y
\thelp
\t  Root-only original kernel identity, client heartbeats and leased CPU QoS.
\t  Thermal and vendor limits retain priority; no vendor KMI layout changes.
'''
MAKEFILE = '\n# Cogan companion ABI\nobj-$(CONFIG_COGAN_BRIDGE) += cogan_bridge.o\n'


def install(source):
    misc = source / 'drivers/misc'
    for name, addition, marker in [('Kconfig', KCONFIG, 'config COGAN_BRIDGE'),
                                   ('Makefile', MAKEFILE, 'CONFIG_COGAN_BRIDGE')]:
        text = (misc / name).read_text()
        if marker in text and not text.endswith(addition):
            raise ValueError(f'Unreviewed existing Cogan bridge in {name}')
    target = misc / 'cogan_bridge.c'
    content = (ROOT / 'kernel-patches/cogan/cogan_bridge.c').read_bytes()
    if target.exists() and target.read_bytes() != content:
        raise ValueError('Unreviewed existing cogan_bridge.c')
    target.write_bytes(content)
    for name, addition in [('Kconfig', KCONFIG), ('Makefile', MAKEFILE)]:
        path = misc / name
        text = path.read_text()
        if not text.endswith(addition):
            path.write_text(text + addition)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    args = parser.parse_args()
    install(args.source)
    print('Cogan built-in companion bridge installed (ABI 1)')

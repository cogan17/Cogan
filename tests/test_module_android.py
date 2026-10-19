"""Parse actual companion responses using Android-like shells and awk implementations.

CI installs mksh, one-true-awk and BusyBox; host dash/mawk remain in the matrix.
This catches syntax accepted by mawk but rejected by the Android awk lexer.
"""
import json
import shlex
import shutil
import tempfile
import unittest
from pathlib import Path

from test_power_mode import AWK, SHELL, FakePhone as Power, write
from test_thermal_monitor import FakePhone as Thermal


class AndroidResponseTests(unittest.TestCase):
    def toolchains(self, base):
        shells = {SHELL}
        awks = {AWK}
        for name in ('mksh', 'dash'):
            if path := shutil.which(name):
                shells.add(path)
        for name in ('original-awk', 'mawk'):
            if path := shutil.which(name):
                awks.add(path)
        if busybox := shutil.which('busybox'):
            # BusyBox selects its sh applet from argv[0], including through a symlink.
            shells.add(busybox)
            wrapper = base / 'busybox-awk'
            write(wrapper, '#!/bin/sh\nexec ' + shlex.quote(busybox) + ' awk "$@"\n')
            wrapper.chmod(0o755)
            awks.add(str(wrapper))
        return [(shell, awk) for shell in sorted(shells) for awk in sorted(awks)]

    def use_tools(self, phone, shell, awk):
        for name, target in (('sh', shell), ('awk', awk)):
            (phone.bin / name).unlink()
            (phone.bin / name).symlink_to(target)

    def test_power_status_after_cpu_apply_with_android_tools(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            for index, (shell, awk) in enumerate(self.toolchains(base)):
                with self.subTest(shell=shell, awk=awk):
                    p = Power(base / str(index))
                    self.use_tools(p, shell, awk)
                    p.report('set', 'MODE', 'hemat')
                    p.set_temp(30)
                    p.step()
                    status = p.report('status')
                    row = next(r for r in status['controls'] if r['node'] == 'policy4')
                    self.assertEqual((row['requested'], row['actual'], row['result']),
                                     ('1500000', '1500000', 'applied'))
                    self.assertEqual(len(p.report('events', '30')), 0)

    def test_power_empty_and_path_readbacks_with_android_tools(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            for index, (shell, awk) in enumerate(self.toolchains(base)):
                with self.subTest(shell=shell, awk=awk):
                    p = Power(base / str(index))
                    self.use_tools(p, shell, awk)
                    write(p.data / 'run/apply.tsv', '')
                    self.assertEqual(p.report('status')['controls'], [])
                    node = 'class/power_supply/battery/input_suspend'
                    write(p.data / 'run/apply.tsv', f'{node}\t1\t1\tapplied\n')
                    self.assertEqual(p.report('status')['controls'],
                                     [dict(node=node, requested='1', actual='1', result='applied')])

    def test_thermal_status_now_and_summary_with_android_tools(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            for index, (shell, awk) in enumerate(self.toolchains(base)):
                with self.subTest(shell=shell, awk=awk):
                    t = Thermal(base / str(index))
                    self.use_tools(t, shell, awk)
                    t.run('sampler.sh', '--once')
                    self.assertEqual(json.loads(t.report('status'))['interval'], 20)
                    self.assertEqual(json.loads(t.report('now'))['main'], 550)
                    self.assertEqual(json.loads(t.report('summary', '3600'))['samples'], 1)


if __name__ == '__main__':
    unittest.main()

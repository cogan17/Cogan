"""Companion regression tests: identity trust, real control readback and recovery."""
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from test_power_mode import FakePhone as Power, write
from test_thermal_monitor import FakePhone as Thermal

ROOT = Path(__file__).resolve().parents[1]


class CompanionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.p = Power(self.base / 'p')
        self.t = Thermal(self.base / 't')
        self.p.env.update(CT_DATA=str(self.t.data), CT_MOD=str(self.t.mod))
        self.t.env.update(CP_DATA=str(self.p.data), CP_MOD=str(self.p.mod), CT_SYS=str(self.p.sys))
        write(self.p.bin / 'uname', '#!/bin/sh\necho 6.1.170-spoofed\n')
        (self.p.bin / 'uname').chmod(0o755)
        write(self.p.base / 'proc/sys/kernel/osrelease', '6.1.177-Cogan-r7\n')
        write(self.p.base / 'proc/version', 'Linux version 6.1.177-Cogan-r7 (compiler)\n')

    def tearDown(self):
        # Stop only the processes belonging to this fixture, including after an assertion fails.
        self.p.report('stop')
        self.t.report('stop')
        self.tmp.cleanup()

    def fake_bridge(self):
        root = self.p.sys / 'kernel/cogan'
        for name, value in {'abi':'1', 'release':'6.1.177-Cogan-r7', 'banner':'Linux version 6.1.177-Cogan-r7',
                            'features':'bridge=1 cpu_qos=1 susfs=1 nomount=1 bbg=1',
                            'limits':'100 100 0 3 0', 'power_client':'0 0', 'thermal_client':'0 0'}.items():
            write(root / name, value + '\n')
        return root

    def test_spoofed_uname_is_not_claimed_to_be_original_without_bridge(self):
        k = self.p.report('status')['kernel']
        self.assertEqual((k['original'], k['verified'], k['source']), (None, 0, 'proc_candidate'))
        self.assertEqual((k['release'], k['uname'], k['different']), ('6.1.177-Cogan-r7', '6.1.170-spoofed', 1))

    def test_both_modules_read_compile_time_identity_and_register(self):
        b = self.fake_bridge()
        self.t.run('sampler.sh', '--once')
        self.p.step()
        for k in (self.p.report('status')['kernel'], json.loads(self.t.report('status'))['kernel']):
            self.assertEqual((k['verified'], k['original']), (1, '6.1.177-Cogan-r7'))
            self.assertIn('susfs=1', k['features'])
        self.assertEqual((b / 'power_client').read_text().strip(), '4')
        self.assertEqual((b / 'thermal_client').read_text().strip(), '5')
        # A regular file is not a QoS driver: writing succeeds but invalid readback must fail closed.
        self.assertEqual(self.p.report('status')['backend'], 'sysfs')
        self.assertEqual(self.p.report('status')['controls'][0]['result'], 'write_failed')

    def test_reset_preserves_original_cpu_limits_and_restores_owner_defaults(self):
        node = self.p.sys / 'devices/system/cpu/cpufreq/policy4/scaling_max_freq'
        write(node, '2000000\n')
        self.p.report('set', 'MODE', 'hemat', 'TARGET_TEMP', '38', 'CHARGE_STOP', '80', 'CHARGE_RESUME', '75')
        self.p.set_temp(30)
        self.p.step()
        self.assertLess(int(node.read_text()), 2000000)
        status = self.p.report('reset')
        self.assertEqual(int(node.read_text()), 2000000)
        self.assertEqual((status['config']['CHARGE_STOP'], status['config']['CHARGE_RESUME']), (95, 90))
        self.assertEqual((status['config']['TARGET_TEMP'], status['config']['AUTOSTART'], status['running']), (42, 0, 0))

    def test_force_retries_changed_cpu_limit_and_reports_actual_values(self):
        self.p.report('set', 'MODE', 'hemat')
        self.p.set_temp(30)
        self.p.step()
        node = self.p.sys / 'devices/system/cpu/cpufreq/policy4/scaling_max_freq'
        write(node, '2400000\n')
        self.p.step()
        row = next(x for x in self.p.report('status')['controls'] if x['node'] == 'policy4')
        self.assertEqual((row['result'], row['actual']), ('conflict', '2400000'))
        self.p.report('set', 'FORCE', '1')
        self.p.step()
        row = next(x for x in self.p.report('status')['controls'] if x['node'] == 'policy4')
        self.assertEqual((row['result'], row['actual'], row['requested']), ('applied', '1500000', '1500000'))

    def test_external_stricter_limit_is_retained_on_stop(self):
        self.p.report('set', 'MODE', 'hemat', 'FORCE', '1')
        self.p.set_temp(30)
        self.p.step()
        node = self.p.sys / 'devices/system/cpu/cpufreq/policy4/scaling_max_freq'
        write(node, '1200000\n')
        self.p.step()
        self.assertLessEqual(int(node.read_text()), 1200000)
        self.p.report('stop')
        self.assertEqual(int(node.read_text()), 1200000)

    def test_no_charging_write_without_ownership(self):
        write(self.p.data / 'switch', 'class/power_supply/battery/input_suspend|0|1\n')
        write(self.p.battery / 'input_suspend', '1\n')  # another controller paused charging
        self.p.step()
        self.p.report('stop')
        self.assertEqual(self.p.node('input_suspend'), '1')

    def test_reset_thermal_keeps_history_and_logs(self):
        self.t.run('sampler.sh', '--once')
        rows = list((self.t.data / 'data').glob('*.tsv'))
        before = rows[0].read_bytes()
        self.t.report('set', 'HOT_TEMP', '50', 'INTERVAL', '60')
        s = json.loads(self.t.report('reset'))
        self.assertEqual((s['hot'], s['interval'], s['autostart'], s['running']), (42, 20, 0, 0))
        self.assertEqual(rows[0].read_bytes(), before)

    def test_invalid_multi_setting_request_is_atomic_and_cannot_inject_config_lines(self):
        self.t.report('set', 'HOT_TEMP', '43')
        before = (self.t.data / 'config').read_bytes()
        for args in [('INTERVAL','30','NOTIFY','1\nINTERVAL=1'), ('HOT_TEMP','50','INTERVAL'), ('HOT_TEMP','050')]:
            self.assertEqual(json.loads(self.t.report('set', *args))['ok'], 0)
            self.assertEqual((self.t.data / 'config').read_bytes(), before)
        self.assertEqual(self.p.report('set','MODE','hemat','FORCE')['ok'], 0)
        self.assertEqual(self.p.report('status')['config']['mode'], 'seimbang')

    def test_stop_survives_boot_service_without_automatic_restart(self):
        self.p.report('stop'); self.t.report('stop')
        self.p.run('service.sh'); self.t.run('service.sh')
        self.assertEqual(self.p.report('status')['running'], 0)
        self.assertEqual(json.loads(self.t.report('status'))['running'], 0)

    def test_apply_saves_starts_and_waits_for_matching_readback(self):
        self.p.set_temp(30)
        r = self.p.report('apply', 'MODE', 'hemat', 'SAVER_CAP', '50', 'CHARGE_CTRL', '0')
        self.assertEqual(r['ok'], 1)
        s = r['status']
        self.assertEqual((s['running'], s['config']['FORCE'], s['state']['big']), (1, 1, 50))
        self.assertTrue(any(x['result'] == 'applied' for x in s['controls']))
        self.assertEqual((self.p.data/'run/apply.request').read_text(), (self.p.data/'run/applied.request').read_text())

    def test_cooling_state_and_peer_detection(self):
        root = self.p.sys / 'class/thermal/cooling_device0'
        for k,v in {'type':'cpu-cooling', 'cur_state':'2', 'max_state':'8'}.items(): write(root/k,v+'\n')
        s=self.p.report('status')
        self.assertEqual(s['cooling'], [{'name':'cpu-cooling','state':2,'max':8}])
        self.assertEqual(s['peer']['installed'], 1)
        self.assertEqual(json.loads(self.t.report('status'))['power']['installed'], 1)

    def test_disabled_peer_and_future_timestamp_are_not_used_for_control(self):
        self.p.monitor = self.t.data
        self.p.monitor_report('Cas cepat', age=-3600)
        self.assertEqual(self.p.step()['source'], 'sensor')

    def test_kernel_qos_backend_requires_positive_ack_and_does_not_write_user_limits(self):
        import os, threading
        self.p.set_temp(30)
        self.p.report('set','MODE','hemat','SAVER_CAP','50')
        root=self.fake_bridge();fifo=root/'limits';fifo.unlink();os.mkfifo(fifo)
        requests=[]
        def driver():
            while True:
                with fifo.open() as f: line=f.read().strip()
                if line=='exit': return
                big,little,ttl=map(int,line.split());requests.append((big,little,ttl))
                with fifo.open('w') as f:
                    f.write(f'{big if ttl else 100} {little if ttl else 100} {ttl} 3 0\n')
        t=threading.Thread(target=driver,daemon=True);t.start()
        try:
            original=self.p.caps()
            self.p.step()
            self.assertEqual((self.p.data/'run/backend').read_text().strip(),'kernel_qos')
            self.assertEqual(requests[0],(50,70,30))
            self.assertEqual(self.p.caps(),original)
            self.assertIn('applied',(self.p.data/'run/apply.tsv').read_text())
            self.p.report('stop')
            self.assertEqual(requests[-1],(0,0,0))
        finally:
            with fifo.open('w') as f:f.write('exit\n')
            t.join(2);self.assertFalse(t.is_alive())
            fifo.unlink();write(fifo,'100 100 0 3 0\n')

    def test_stale_lock_from_previous_boot_or_reused_pid_is_recovered(self):
        import os
        lock = self.p.data/'api.lock'
        write(lock/'pid', str(os.getpid())+'\n')
        write(lock/'boot_id', 'previous-boot\n')
        self.assertEqual(self.p.report('set','TARGET_TEMP','40'), {'ok':1})
        self.assertFalse(lock.exists())

    def test_native_cpu_cooling_prevents_extra_step_when_temperature_is_flat(self):
        root=self.p.sys/'class/thermal/cooling_device0'
        for k,v in {'type':'cpu-cooling','cur_state':'2','max_state':'8'}.items():write(root/k,v+'\n')
        self.p.set_temp(45)
        self.assertEqual(self.p.step()['level'],0)
        self.p.set_temp(45.5)
        self.assertEqual(self.p.step()['level'],1)
        self.assertEqual(self.p.step()['level'],1)

    def test_external_stronger_game_boost_is_not_reduced(self):
        node=self.p.cpuctl/'top-app/cpu.uclamp.min'
        write(node,'50.00\n')
        self.p.report('set','MODE','game','FORCE','1')
        self.p.step()
        self.assertEqual(node.read_text().strip(),'50.00')
        self.p.report('stop')
        self.assertEqual(node.read_text().strip(),'50.00')

    def test_config_directory_does_not_report_save_success(self):
        (self.p.data/'config').mkdir(parents=True)
        (self.t.data/'config').mkdir(parents=True)
        self.assertEqual(self.p.report('set','TARGET_TEMP','40')['ok'],0)
        self.assertEqual(json.loads(self.t.report('set','HOT_TEMP','40'))['ok'],0)

    def test_61_compatibility_does_not_require_branding_or_a_specific_sublevel(self):
        self.t.env['CT_PROC'] = str(self.p.base / 'proc')
        for release in ('6.1.0-android14', '6.1.138-stock', '6.1.177-Cogan-r3', '6.1.999-custom'):
            write(self.p.base / 'proc/sys/kernel/osrelease', release + '\n')
            for result in (self.p.report('status'), json.loads(self.t.report('status'))):
                kernel = result['kernel']
                self.assertEqual((kernel['compat_61'], kernel['mode']), (1, 'sysfs_compat'))
                self.assertEqual((kernel['bridge'], kernel['verified'], kernel['original']), (0, 0, None))
                self.assertEqual(kernel['release'], release)
        self.p.report('mode', 'hemat'); self.p.set_temp(30); self.p.step()
        self.assertLess(self.p.caps()['policy4'], 3000000)
        write(self.p.base / 'proc/sys/kernel/osrelease', '6.10.1-unrelated\n')
        self.assertEqual(self.p.report('status')['kernel']['compat_61'], 0)

    def test_native_bridge_uses_abi_instead_of_branding_and_rejects_unknown_abi(self):
        root = self.fake_bridge()
        write(root / 'release', '6.1.0-generic\n')
        kernel = self.p.report('status')['kernel']
        self.assertEqual((kernel['mode'], kernel['original'], kernel['verified']), ('native', '6.1.0-generic', 1))
        write(root / 'abi', '2\n')
        kernel = self.p.report('status')['kernel']
        self.assertEqual((kernel['mode'], kernel['original'], kernel['verified']), ('sysfs_compat', None, 0))

    def test_bridge_detection_reads_virtual_attributes_even_when_size_is_zero(self):
        root = self.fake_bridge()
        release = root / 'release'; release.unlink()
        release.symlink_to('/proc/sys/kernel/osrelease')
        self.assertEqual(release.stat().st_size, 0)
        self.assertEqual(self.p.report('status')['kernel']['bridge'], 1)

    def test_light_reads_do_not_open_cooling_inventory_and_explicit_read_does(self):
        import os
        root = self.p.sys / 'class/thermal/cooling_device0'
        root.mkdir(parents=True)
        os.mkfifo(root / 'cur_state')  # A read would block; light endpoints must not open it.
        try:
            for phone, args in ((self.p, ('live',)), (self.p, ('status', 'brief')), (self.t, ('status', 'brief'))):
                result = subprocess.run([str(phone.bin / 'sh'), str(phone.mod / 'report.sh'), *args],
                                        env=phone.env, capture_output=True, text=True, timeout=3, check=True)
                self.assertNotIn('cooling', json.loads(result.stdout))
            self.assertNotIn('kernel', self.p.report('live'))
        finally:
            (root / 'cur_state').unlink()
        for name, value in {'type': 'cpu-cooling', 'cur_state': '2', 'max_state': '8'}.items():
            write(root / name, value + '\n')
        expected = [dict(name='cpu-cooling', state=2, max=8)]
        self.assertEqual(self.p.report('cooling'), expected)
        self.assertEqual(json.loads(self.t.report('cooling')), expected)

    def test_sensor_and_cooling_inventory_do_not_spawn_cat_for_each_node(self):
        import shlex
        calls = self.base / 'cat-calls'
        for phone in (self.p, self.t):
            write(phone.bin / 'cat', '#!/bin/sh\nprintf "%s\\n" "$*" >> ' + shlex.quote(str(calls)) + '\nexec /bin/cat "$@"\n')
            (phone.bin / 'cat').chmod(0o755)
        for index in range(60):
            zone = self.p.sys / f'class/thermal/thermal_zone{index + 10}'
            write(zone / 'type', f'cpu{index}\n'); write(zone / 'temp', '51900\n')
            cooling = self.p.sys / f'class/thermal/cooling_device{index}'
            for name, value in {'type': f'cpu{index}-cooling', 'cur_state': '0', 'max_state': '8'}.items():
                write(cooling / name, value + '\n')
        self.assertEqual(self.p.report('status')['main'], 519)
        self.assertEqual(json.loads(self.t.report('now'))['main'], 519)
        node_calls = [line for line in calls.read_text().splitlines() if '/thermal_zone' in line or '/cooling_device' in line]
        self.assertEqual(node_calls, [])


class BridgeSourceTests(unittest.TestCase):
    def test_additive_install_is_repeatable_and_rejects_foreign_bridge(self):
        import importlib.util
        spec=importlib.util.spec_from_file_location('bridge_installer',ROOT/'scripts/install_cogan_bridge.py')
        m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
        with tempfile.TemporaryDirectory() as d:
            src=Path(d); (src/'drivers/misc').mkdir(parents=True)
            for name in ('Makefile','Kconfig'): write(src/'drivers/misc'/name, '# upstream\n')
            m.install(src); first=(src/'drivers/misc/Makefile').read_bytes();m.install(src)
            self.assertEqual(first,(src/'drivers/misc/Makefile').read_bytes())
            write(src/'drivers/misc/cogan_bridge.c','unreviewed\n')
            with self.assertRaises(ValueError): m.install(src)

    def test_independent_modules_ship_identical_abi_helper(self):
        self.assertEqual((ROOT/'modules/power-mode/bridge.sh').read_bytes(),(ROOT/'modules/thermal-monitor/bridge.sh').read_bytes())
        self.assertEqual((ROOT/'modules/power-mode/webroot/client.js').read_bytes(),
                         (ROOT/'modules/thermal-monitor/webroot/client.js').read_bytes())


if __name__ == '__main__': unittest.main()

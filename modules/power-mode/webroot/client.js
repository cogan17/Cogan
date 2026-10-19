/* Shared by the independently installable Cogan companions. */
(() => {
  'use strict';
  const text = (id, value) => {
    const el = document.getElementById(id), next = String(value);
    if (el && el.textContent !== next) { el.textContent = next; markup.delete(el); }
  };
  const markup = new WeakMap();
  const html = (id, value) => {
    const el = document.getElementById(id);
    if (el && markup.get(el) !== value) { el.innerHTML = value; markup.set(el, value); }
  };
  const shortKernel = release => {
    const value = String(release || ''), version = value.match(/\b6\.1\.\d+\b/);
    if (!version) return 'Kernel ' + (value.match(/^\d+\.\d+\.\d+/)?.[0] || 'tidak diketahui');
    const revision = value.match(/(?:^|[-_])r(\d+)(?:[-_]|$)/i);
    return (/cogan/i.test(value) ? 'Cogan' + (revision ? ' r' + revision[1] : '') : 'GKI') + ' · ' + version[0];
  };
  const quote = value => "'" + String(value).replace(/'/g, "'\\''") + "'";

  function create(script) {
    let sequence = 0, running = false, revision = 0;
    const queue = [], reads = new Map();

    function native(args) {
      return new Promise((resolve, reject) => {
        if (typeof ksu === 'undefined') return reject(new Error('Buka dari WebUI root manager'));
        const callback = 'cogan_stream_' + Date.now() + '_' + sequence++;
        const out = [], err = [];
        let settled = false;
        const timeout = setTimeout(() => finish(new Error('Perintah belum selesai; periksa status sebelum mencoba lagi')), 120000);
        function finish(error, errno = 0, stdout = out.join('\n'), stderr = err.join('\n')) {
          if (settled) return;
          settled = true; clearTimeout(timeout);
          // Some managers send an error event immediately after a nonzero exit.
          setTimeout(() => { delete window[callback]; }, 1000);
          if (error) reject(error); else resolve({errno, stdout, stderr});
        }
        const event = (name, data) => {
          if (name === 'exit') finish(null, Number(data));
          else if (name === 'error') finish(new Error(data?.message || String(data || 'Perintah gagal')));
        };
        if (typeof ksu.spawn === 'function') {
          window[callback] = {
            stdout: {emit: (name, data) => { if (!settled && name === 'data') out.push(String(data)); }},
            stderr: {emit: (name, data) => { if (!settled && name === 'data') err.push(String(data)); }},
            emit: event, exit: code => event('exit', code), error: error => event('error', error)
          };
          try {
            // Native managers join arguments into a shell command; quote each one.
            ksu.spawn('sh', JSON.stringify([script, ...args].map(quote)), '{}', callback);
          } catch (error) { finish(error); }
        } else if (typeof ksu.exec === 'function') {
          window[callback] = (errno, stdout, stderr) => finish(null, Number(errno), stdout, stderr);
          try { ksu.exec(['sh', script, ...args].map(quote).join(' '), '{}', callback); }
          catch (error) { finish(error); }
        } else finish(new Error('API shell root manager tidak tersedia'));
      });
    }

    async function pump() {
      if (running || !queue.length) return;
      running = true;
      const job = queue.shift();
      try {
        const result = await native(job.args), command = job.args[0];
        if (result.errno !== 0) throw new Error(`Perintah ${command} gagal (kode ${result.errno}): ${String(result.stderr || 'tanpa keterangan').trim().slice(0, 200)}`);
        let data;
        try { data = JSON.parse(result.stdout); }
        catch (error) { throw new Error(`Respons ${command} bukan JSON lengkap: ${error.message.slice(0, 160)}`); }
        if (!data || typeof data !== 'object') throw new Error(`Respons ${command} tidak valid`);
        if (data.ok === 0 && command !== 'detect') throw new Error(data.error || 'Perintah belum berhasil');
        job.resolve(data);
      } catch (error) { job.reject(error); }
      finally {
        if (reads.get(job.key) === job.promise) reads.delete(job.key);
        running = false; pump();
      }
    }

    function report(value, {background = false} = {}) {
      const args = String(value).trim().split(/\s+/), key = args.join(' ');
      if (args.some(arg => !/^[A-Za-z0-9_.-]+$/.test(arg))) return Promise.reject(new Error('Argumen tidak valid'));
      const read = /^(status|live|now|summary|events|cooling)$/.test(args[0]);
      if (read && reads.has(key)) return reads.get(key);
      if (!read) revision++;
      let resolve, reject;
      const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
      const job = {args, key, promise, resolve, reject, background};
      if (read) reads.set(key, promise);
      if (background) queue.push(job);
      else {
        const firstBackground = queue.findIndex(item => item.background);
        queue.splice(firstBackground < 0 ? queue.length : firstBackground, 0, job);
      }
      // Queue in this turn so a user action can precede pending background work.
      Promise.resolve().then(pump);
      return promise;
    }
    return {report, get revision() { return revision; }};
  }

  function poll(task, interval = 5000) {
    let timer, active = false, again = false, stopped = false;
    function schedule(delay) {
      clearTimeout(timer);
      if (!stopped && !document.hidden) timer = setTimeout(tick, delay);
    }
    async function tick() {
      if (active) { again = true; return; }
      if (stopped || document.hidden) return;
      active = true;
      try { await task(); } catch (_) { /* The page displays read errors. */ }
      finally { active = false; schedule(again ? 0 : interval); again = false; }
    }
    const visible = () => document.hidden ? clearTimeout(timer) : schedule(0);
    document.addEventListener('visibilitychange', visible);
    const stop = () => { stopped = true; clearTimeout(timer); document.removeEventListener('visibilitychange', visible); };
    window.addEventListener('pagehide', stop, {once: true});
    schedule(0);
    return {poke: () => active ? again = true : schedule(0), stop};
  }

  let actionBusy = false;
  async function action(button, message, task) {
    if (actionBusy) return;
    actionBusy = true;
    const controls = [...document.querySelectorAll('button[data-action]')];
    if (!controls.includes(button)) controls.push(button);
    const disabled = controls.map(control => control.disabled);
    controls.forEach(control => control.disabled = true);
    button.setAttribute('aria-busy', 'true');
    text('actionStatus', message);
    document.getElementById('actionStatus')?.classList.remove('hidden');
    document.getElementById('actionStatus')?.classList.add('working');
    try {
      await new Promise(resolve => requestAnimationFrame(() => setTimeout(resolve, 0)));
      await task();
    } finally {
      actionBusy = false;
      controls.forEach((control, index) => control.disabled = disabled[index]);
      button.removeAttribute('aria-busy');
      document.getElementById('actionStatus')?.classList.remove('working');
    }
  }
  function kernel(sample, peer, name) {
    const value = sample.kernel;
    if (!value) return;
    text('kernelTitle', shortKernel(value.original || value.release));
    text('bridgeStatus', value.bridge ? 'Bridge native aktif' : value.compat_61 ? 'Kompatibilitas 6.1 · sysfs' : 'Akses sysfs perangkat');
    text('identityLabel', value.verified ? 'Identitas asli · terverifikasi' : 'Identitas dari ' + (value.source === 'uname_only' ? 'uname' : '/proc') + ' · belum terverifikasi');
    text('originalKernel', value.original || value.release || 'Tidak tersedia');
    text('shownKernel', 'uname: ' + (value.uname || '—') + (value.different ? ' · berbeda dari sumber di atas' : ''));
    text('kernelFeatures', value.features || 'Fitur bawaan belum dikonfirmasi.');
    text('kernelBanner', value.banner || 'Info build tidak tersedia.');
    const client = raw => { const [code, age] = String(raw || '').split(' ').map(Number); return code > 0 ? 'aktif (' + (age || 0) + ' dtk)' : 'belum aktif'; };
    text('clients', value.bridge ? 'Dikenali kernel: Power ' + client(value.power_client) + ' · Thermal ' + client(value.thermal_client) : 'Bridge native memerlukan driver Cogan Bridge dalam build kernel 6.1. Kontrol sysfs tetap mengikuti dukungan perangkat.');
    text('peerStatus', name + ': ' + (peer?.installed ? (peer.running ? 'aktif' : 'berhenti') : 'belum terpasang') + (peer?.version ? ' · ' + peer.version : ''));
  }
  function cooling(devices) {
    text('coolingTitle', 'Cooling kernel · ' + devices.filter(device => device.state > 0).length + ' aktif');
    text('coolingInfo', devices.length ? devices.map(device => `${device.name}: ${device.state}/${device.max}`).join(' · ') : 'Tidak ada cooling device yang dapat dibaca.');
  }
  window.CoganUI = {create, poll, action, text, html, shortKernel, kernel, cooling};
})();

/* Native managers dispatch line events; exercise the actual shared client. */
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../modules/power-mode/webroot/client.js'), 'utf8');
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));

function fixture(bridge = {}) {
  const listeners = {}, window = {addEventListener: (name, callback) => listeners[name] = callback};
  const document = {hidden: false, addEventListener: (name, callback) => listeners[name] = callback,
    removeEventListener: name => delete listeners[name]};
  const context = vm.createContext({window, document, ksu: bridge, setTimeout, clearTimeout, console});
  vm.runInContext(source, context);
  return {ui: window.CoganUI, window, document, listeners};
}

test('streaming transport returns immediately and reconstructs multiline Unicode JSON', async () => {
  let f, callback;
  f = fixture({spawn(command, args, options, name) {
    assert.equal(command, 'sh'); assert.equal(options, '{}'); callback = name;
    setTimeout(() => {
      const events = f.window[name];
      events.stdout.emit('data', '{"ok":1,'); events.stdout.emit('data', '"text":"suhu 42 °C"}');
      events.emit('exit', 0);
    }, 40);
  }, exec() { throw Error('blocking exec must not be called'); }});
  const client = f.ui.create('/data/adb/modules/cogan_power/report.sh');
  const promise = client.report('live');
  assert.equal(typeof promise.then, 'function');
  assert.equal((await promise).text, 'suhu 42 °C');
  // Accept managers that send an error event after the exit callback.
  f.window[callback].emit('error', {message: 'late event'});
});

test('one active shell, coalesced duplicate reads and actions before queued background reads', async () => {
  let f, active = 0, maximum = 0;
  const calls = [];
  f = fixture({spawn(command, args, options, name) {
    active++; maximum = Math.max(maximum, active);
    calls.push(JSON.parse(args).slice(1).map(value => value.slice(1, -1)).join(' '));
    setTimeout(() => {
      active--; f.window[name].stdout.emit('data', '{"ok":1}'); f.window[name].emit('exit', 0);
    }, 25);
  }});
  const client = f.ui.create('/data/adb/modules/cogan_power/report.sh');
  const first = client.report('live', {background: true});
  assert.equal(first, client.report('live', {background: true}));
  await sleep(5);
  const summary = client.report('summary 3600', {background: true});
  const mode = client.report('mode hemat');
  await Promise.all([first, summary, mode]);
  assert.deepEqual(calls, ['live', 'mode hemat', 'summary 3600']);
  assert.equal(maximum, 1); assert.equal(client.revision, 1);
});

test('a nonzero exit cannot become success because stdout is valid JSON', async () => {
  let f;
  f = fixture({spawn(command, args, options, name) {
    setTimeout(() => {
      f.window[name].stdout.emit('data', '{"ok":1}');
      f.window[name].stderr.emit('data', 'permission denied'); f.window[name].emit('exit', 7);
    }, 0);
  }});
  await assert.rejects(f.ui.create('/module/report.sh').report('apply'), /kode 7.*permission denied/);
});

test('malformed JSON is diagnosed and a later retry can succeed', async () => {
  let f, broken = true;
  f = fixture({spawn(command, args, options, name) {
    setTimeout(() => {
      f.window[name].stdout.emit('data', broken ? '{"controls":,}' : '{"controls":[]}');
      broken = false; f.window[name].emit('exit', 0);
    }, 0);
  }});
  const client = f.ui.create('/module/report.sh');
  await assert.rejects(client.report('live'), /Respons live bukan JSON lengkap/);
  assert.equal((await client.report('live')).controls.length, 0);
});

test('fallback exec remains compatible and shell arguments are quoted', async () => {
  let f, command;
  f = fixture({exec(cmd, options, name) {
    command = cmd; setTimeout(() => f.window[name](0, '{"ok":1}', ''), 0);
  }});
  await f.ui.create("/module/it's a test/report.sh").report('set INTERVAL 10');
  assert(command.includes("'it") === false);
  assert(command.includes("it'\\''s a test"));
  assert(command.endsWith("'set' 'INTERVAL' '10'"));
  await assert.rejects(f.ui.create('/module/report.sh').report('set INTERVAL 10;reboot'), /Argumen tidak valid/);
});

test('backend errors are rejected except detailed charger detection results', async () => {
  let f;
  f = fixture({exec(command, options, name) { setTimeout(() => f.window[name](0, '{"ok":0,"error":"unsupported"}', ''), 0); }});
  const client = f.ui.create('/module/report.sh');
  await assert.rejects(client.report('set INTERVAL 1'), /unsupported/);
  assert.equal((await client.report('detect')).ok, 0);
});

test('polling never overlaps, pauses while hidden, and resumes on visibility', async () => {
  const f = fixture(); let active = 0, maximum = 0, calls = 0;
  const poller = f.ui.poll(async () => { calls++; active++; maximum = Math.max(maximum, active); await sleep(25); active--; }, 10);
  await sleep(50); f.document.hidden = true; f.listeners.visibilitychange();
  await sleep(45); const paused = calls; await sleep(45); assert.equal(calls, paused);
  f.document.hidden = false; f.listeners.visibilitychange(); await sleep(45); poller.stop();
  assert(calls > paused); assert.equal(maximum, 1);
});

test('compact identity keeps the release and revision while hiding compiler/hash text', () => {
  const f = fixture();
  assert.equal(f.ui.shortKernel('6.1.177-Cogan-r3-3f08838cb'), 'Cogan r3 · 6.1.177');
  assert.equal(f.ui.shortKernel('6.1.138-android14-11-gabcdef-ab14396278'), 'GKI · 6.1.138');
});

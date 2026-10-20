// Real Firefox WebDriver BiDi acceptance, stdlib Node only. No product network.
// node journal_browser.mjs REPORT.html [SCREENSHOT_PREFIX]
import {spawn, spawnSync} from 'node:child_process';
import {mkdtempSync, writeFileSync} from 'node:fs';
import {resolve} from 'node:path';
import assert from 'node:assert/strict';
const profile = mkdtempSync('/tmp/journal-browser-');
writeFileSync(profile + '/user.js', 'user_pref("app.update.enabled",false);user_pref("browser.shell.checkDefaultBrowser",false);user_pref("datareporting.policy.dataSubmissionEnabled",false);');
const zoomMode = process.argv.includes('--zoom200');
if (zoomMode) {
  // Firefox's real global browser zoom, in this disposable profile only.
  const setup = spawnSync('python3.12', ['-c', `import sqlite3,sys
c=sqlite3.connect(sys.argv[1]);c.executescript("CREATE TABLE groups(id INTEGER PRIMARY KEY,name TEXT NOT NULL);CREATE TABLE settings(id INTEGER PRIMARY KEY,name TEXT NOT NULL);CREATE TABLE prefs(id INTEGER PRIMARY KEY,groupID INTEGER,settingID INTEGER NOT NULL,value BLOB,timestamp INTEGER NOT NULL DEFAULT 0);INSERT INTO settings VALUES(1,'browser.content.full-zoom');INSERT INTO prefs VALUES(1,NULL,1,2.0,0);PRAGMA user_version=6;");c.commit()`, profile + '/content-prefs.sqlite']);
  if (setup.status) throw new Error(String(setup.stderr));
}
const port = zoomMode ? 9232 : 9231;
const child = spawn('firefox', ['--headless', '--no-remote', '--profile', profile,
  '--width','1280','--height','1000','--remote-debugging-port', String(port), 'about:blank'], {env: {...process.env, XDG_CACHE_HOME:profile}});
let socket, sequence = 0, pending = new Map(), log = '';
const deadline = setTimeout(() => { console.error(log); child.kill(); process.exit(1); }, 110000);
function request(method, params) {
  const id = ++sequence;
  return new Promise((resolve, reject) => {
    pending.set(id, {resolve, reject}); socket.send(JSON.stringify({id, method, params}));
  });
}
try {
  await new Promise((resolve, reject) => {
    child.stderr.on('data', d => {log += String(d); if (log.includes('WebDriver BiDi listening')) resolve();});
    child.on('exit', c => reject(new Error('Firefox exited ' + c)));
  });
  socket = new WebSocket('ws://127.0.0.1:' + port + '/session');
  await new Promise((resolve, reject) => {socket.onopen = resolve; socket.onerror = reject;});
  socket.onmessage = event => {
    const message = JSON.parse(event.data), p = pending.get(message.id);
    if (!p) return;
    pending.delete(message.id);
    if (message.type === 'error') p.reject(new Error(JSON.stringify(message))); else p.resolve(message.result);
  };
  await request('session.new', {capabilities: {}});
  const {context} = await request('browsingContext.create', {type:'tab'});
  const evaluate = async expression => {
    const r = await request('script.evaluate', {expression: 'JSON.stringify((' + expression + '))',
      target:{context}, awaitPromise:true});
    if (r.type === 'exception') throw new Error(JSON.stringify(r));
    return JSON.parse(r.result.value);
  };
  const click = text => evaluate(`(()=>{const b=[...document.querySelectorAll('button,summary')].find(e=>e.textContent.startsWith(${JSON.stringify(text)})); if(!b)throw Error('missing control'); b.click();return true;})()`);
  const screenshot = async suffix => {
    if (!process.argv[3]) return;
    const r = await request('browsingContext.captureScreenshot', {context});
    writeFileSync(process.argv[3] + '-' + suffix + '.png', Buffer.from(r.data,'base64'));
  };
  if (!zoomMode) await request('browsingContext.setViewport', {context, viewport:{width:1280,height:900}});
  await request('browsingContext.navigate', {context,url:'file://' + resolve(process.argv[2]),wait:'complete'});
  const before = await evaluate(`JSON.parse(document.getElementById('data').textContent).journal`);
  const initial = await evaluate(`({concerns:document.querySelectorAll('.journal-concern').length,routine:document.querySelectorAll('.journal-event').length,open:document.querySelectorAll('.journal details[open]').length,text:document.querySelector('.journal').innerText,width:document.documentElement.scrollWidth,viewport:innerWidth})`);
  assert(initial.concerns <= 3); assert.equal(initial.routine,0); assert.equal(initial.open,0);
  assert(initial.text.includes('Coverage:')); assert(!initial.text.includes('source_digest'));
  assert(initial.width <= initial.viewport);
  if (before.events.some(e => e.limitations.some(l => l.includes('Conflicting'))))
    assert(initial.text.includes('conflicting or changed variants'), 'source conflicts must remain visible');
  await screenshot(zoomMode ? 'overview-zoom200' : 'overview');
  if (initial.concerns) {
    await evaluate(`(()=>{document.querySelector('.journal-concern').click();return true;})()`);
    await click('Evidence and provenance');
    assert(await evaluate(`document.querySelector('.journal-detail details').open`));
    await evaluate(`(()=>{document.querySelector('.journal-detail details').scrollIntoView({block:'start'});return true;})()`);
    await screenshot(zoomMode ? 'evidence-zoom200' : 'evidence');
    await evaluate(`(()=>{scrollTo(0,0);return true;})()`);
    await click('Back to overview');
  }
  await click('Show all ');
  assert.equal(await evaluate(`document.querySelectorAll('.journal-concern').length`), Number(/Show all (\d+) concerns/.exec(initial.text)[1]));
  await click('Back to overview');
  await click('Explore history');
  const target = before.events.filter(e => e.kind === 'attempt' && e.summary === 'exit 0 recorded').pop();
  assert(target, 'fixture needs a routine event outside the initial view');
  await evaluate(`(()=>{const s=document.querySelector('.journal input[type=search]');s.value=${JSON.stringify(target.id)};s.dispatchEvent(new Event('input'));return true;})()`);
  assert.equal(await evaluate(`document.querySelectorAll('.journal-event').length`),1);
  await evaluate(`(()=>{document.querySelector('.journal-event').click();return true;})()`);
  assert((await evaluate(`document.querySelector('.journal-detail').textContent`)).includes(target.id));
  await click('Collapse detail'); await click('Expand detail');
  await click('Back to overview'); await click('Explore history');
  assert.equal(await evaluate(`document.querySelector('.journal input[type=search]').value`),target.id);
  assert.deepEqual(await evaluate(`JSON.parse(document.getElementById('data').textContent).journal`),before);
  // Native keyboard path, actual rendered focus, not a DOM-only test.
  await evaluate(`(()=>{document.querySelector('.journal input[type=search]').focus();return true;})()`);
  await request('input.performActions',{context,actions:[{type:'key',id:'keyboard',actions:[{type:'keyDown',value:'\uE004'},{type:'keyUp',value:'\uE004'}]}]});
  assert(await evaluate(`document.activeElement.tagName === 'BUTTON'`));
  assert(await evaluate(`getComputedStyle(document.activeElement).outlineStyle !== 'none'`));
  await request('input.performActions',{context,actions:[{type:'key',id:'keyboard',actions:[{type:'keyDown',value:'\uE007'},{type:'keyUp',value:'\uE007'}]}]});
  assert(await evaluate(`[...document.querySelectorAll('.journal button')].some(b=>b.textContent.startsWith('Collapse routine') && b.getAttribute('aria-expanded')==='true')`));
  if (!zoomMode) await request('browsingContext.setViewport',{context,viewport:{width:390,height:844}});
  assert(await evaluate(`document.documentElement.scrollWidth <= innerWidth`));
  await screenshot(zoomMode ? 'detail-zoom200' : 'narrow');
  const zoom = await evaluate(`({width:innerWidth,dpr:devicePixelRatio,overflow:document.documentElement.scrollWidth>innerWidth})`);
  if (zoomMode) assert.equal(zoom.dpr,2,'real global browser zoom must be 200%');
  assert(!zoom.overflow);
  assert.deepEqual(await evaluate(`JSON.parse(document.getElementById('data').textContent).journal`),before);
  console.log(JSON.stringify({checks:'overview, evidence, navigation, all-history search, export invariance, keyboard, layout',zoomMode,events:before.events.length,initial,zoom}));
} finally {
  clearTimeout(deadline); socket?.close(); child.kill();
}

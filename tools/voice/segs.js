// アプリの speechSegs をそのまま動かして、録音する区切り（文・読み・間・ハッシュ）を書き出す
const { chromium } = require('playwright');
const fs = require('fs');
(async () => {
  const app = process.argv[2];
  const b = await chromium.launch();
  const p = await b.newPage();
  const errs = []; p.on('pageerror', e => errs.push(e.message));
  await p.route('**/*', r => r.request().url().startsWith('file://') ? r.continue() : r.abort());
  await p.goto('file:///home/claude/src/' + app + '.offline.html');
  await p.waitForTimeout(1500);
  const out = await p.evaluate(() => {
    const items = [];
    const add = (rk, segs, tail) => items.push({ rk, tail, segs: segs.map(s => ({ t: s.text, g: s.gap || s.pause || SPEECH_PAUSE, h: recH(s.text) })) });
    DATA.cloze.forEach(q => add(q.id, speechSegs(q), 600));
    const pids = [...new Set(DATA.cloze.map(q => q.pid))];
    pids.forEach(pid => { const [a, b] = pid.split('-');
      add('pid:' + pid, [{ text: `問題${a}の${b}。${normSpeech((PT[pid] || '').replace(/（/g, '、').replace(/）/g, ''))}。`, pause: 1000 }], 750); });
    const q = { id: 'sample', title: '', t: '個人事業者のその年の12月31日の属する課税期間の確定申告書の提出期限は、その年の翌年3月31日とする。' };
    add('sample', speechSegs(q), 300);
    return items;
  });
  fs.writeFileSync(app + '.segs.json', JSON.stringify(out));
  const nseg = out.reduce((s, x) => s + x.segs.length, 0), nch = out.reduce((s, x) => s + x.segs.reduce((a, y) => a + y.t.length, 0), 0);
  console.log(app, 'items', out.length, 'segs', nseg, 'chars', nch, 'errors', errs.slice(0, 3));
  await b.close();
})();

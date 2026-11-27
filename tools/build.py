#!/usr/bin/env python3
"""理論アプリのオフライン版（ホーム画面に追加して使うWebアプリ）を作る。

使い方:
    python3 tools/build.py sozoku  path/to/相続税アプリ.html
    python3 tools/build.py shohi   path/to/消費税アプリ.html
    python3 tools/build.py hojin   path/to/法人税アプリ.html

入力は claude.ai で公開しているアプリのHTML（Artifact の index.html）。
出力は <app>/ の index.html（起動用）・app.bin（暗号化した本体）・sw.js・manifest.webmanifest・key.json。

暗号化のしくみ:
  - 本体のHTMLを gzip で縮め、毎回ランダムな鍵（AES-256-GCM）で暗号化する。
  - その鍵を公開鍵（tools/pubkey.pem, RSA-OAEP/SHA-256）で包んで app.bin の先頭に置く。
  - 秘密鍵はパスワードで暗号化して tools/key.json に置いてある（パスワードはこのリポジトリにはない）。
  - 端末では最初の1回だけパスワードを入れて秘密鍵を取り出し、その端末に保存する。
  このため、作り直し（build）にパスワードは要らない。
"""
import base64, gzip, hashlib, json, os, re, shutil, sys, time

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "tools")

APPS = {
    "sozoku": {"name": "相続税 理論", "short": "相続税", "id": "sozoku-riron", "key": "sozoku-drill-v1", "light": "#1E4A90"},  # 2026-11-27 アイコンの紺色に
    "shohi": {"name": "消費税 理論", "short": "消費税", "id": "shohi-riron", "key": "shohi-drill-v1"},
    # 法人税（2026-11-27〜）：録音の音声はない（アプリの側で読み上げの音声の設定も外してある）
    "hojin": {"name": "法人税 理論", "short": "法人税", "id": "hojin-riron", "key": "hojin-drill-v1", "rec": False, "light": "#C36A65", "icon": "icon4"},
}
THEME_LIGHT, THEME_DARK = "#28A000", "#0F141B"

# 録音の声（2026-11-27〜。VOICEVOX で作った読み上げ。作り方は tools/voice/README.md）
#   tools/voices/<app>.json があるアプリだけ入れる。中身は {声: {問題の rk: [ファイル名, ハッシュ, 開始秒の一覧]}}。
#   音声ファイルは <app>/voice/<声>/<ファイル名>（暗号化してある。形式は app.bin と同じ考えで先頭が RIA1）。
VOICE_INFO = {  # 声: (設定に出す名前, クレジット)
    "no7": ("No.7（女性）", "VOICEVOX:No.7"),
    "aoyama": ("青山龍星（男性）", "VOICEVOX:青山龍星"),
}
STATIC = ["icon3-180.png", "icon3-192.png", "icon3-512.png"]


def must_sub(pattern, repl, s, count=1, flags=0, what=""):
    new, n = re.subn(pattern, repl, s, count=0, flags=flags)
    if n != count:
        sys.exit(f"build: '{what or pattern[:40]}' の置き換え箇所が {n} か所でした（{count} か所のはず）。アプリ側の変更に合わせて build.py を直してください。")
    return new


def offline_patch(html, app):
    """claude.ai 版のHTMLを、オフラインで動く形に直す。"""
    a = APPS[app]
    # 1) Web フォントは読み込まない（iPhone・iPad のヒラギノで表示する）
    html, n = re.subn(r'<link rel="(?:preconnect|stylesheet)" href="https://fonts\.(?:googleapis|gstatic)\.com[^"]*"[^>]*>\n?', "", html)
    if n == 0:
        sys.exit("build: Google Fonts の読み込みが見つかりません")
    # 2) 録音した音声（自然な音声）は使わず、端末の音声で読み上げる
    if a.get("rec", True):
        html = must_sub(r"^const REC=\{.*\};?$", "const REC={};", html, flags=re.M, what="const REC")
        html = must_sub(r'row\("読み上げの音声",.*?opt\("tts",\[\["device","端末の音声"\],\["rec","録音の音声"\]\]\)\)\+', "", html, what="読み上げの音声の設定")
    # tts の初期値はアプリ側で "device"。録音を外した以上 recOK も成り立たないため、ここでの差し替えは不要
    # 2b) 録音の声（VOICEVOX）を入れる。目録がなければ何もしない
    html = voice_patch(html, app)
    # 3) 画面上部には「オフライン版」を出さない（設定の「記録の管理」に説明を置く）
    html = must_sub(r'<span class="sync" id="sync"></span>', '<span class="sync" id="sync"></span>', html, what="sync 表示")
    html = must_sub(r'const secC=sec\("記録の管理",\n', 'const secC=sec("記録の管理",\n    row("オフライン版","通信がなくても使えるよう、この端末に保存しているアプリです。記録はこの端末だけに保存されます。claude.ai版と記録を移すときは、下の「記録の書き出し」と「記録の読み込み」を使います。","")+\n', html, what="記録の管理")
    # 4) ホーム画面に追加したときの名前・アイコン
    head = (
        '<link rel="manifest" href="manifest.webmanifest">'
        '<link rel="apple-touch-icon" href="icon3-180.png">'
        '<meta name="apple-mobile-web-app-capable" content="yes">'
        '<meta name="mobile-web-app-capable" content="yes">'
        f'<meta name="apple-mobile-web-app-title" content="{a["short"]}">'
        # 2026-11-25：black-translucent はやめた。iOS 26.1 以降、時刻などの表示の下まで広げたホーム画面アプリには、
        # iOS が上部にぼかしをかける（ページからは止められない。Apple の回答は「この指定を外す」）。
        # 指定はホーム画面に追加したときに決まるので、効くのは入れ直したあと。入れ直す前のアプリは今までどおり動く。
        f'<meta name="theme-color" content="{a.get("light", THEME_LIGHT)}" media="(prefers-color-scheme: light)">'
        f'<meta name="theme-color" content="{THEME_DARK}" media="(prefers-color-scheme: dark)">'
    )
    # ローダーと同じ画面の指定にそろえる（開いた直後に指定が変わると、iPadで一瞬だけ拡大して見えるため）
    head = head.replace("icon3-", a.get("icon", "icon3") + "-")  # 法人税は色を変えたので名前を変える（iOS のアイコンのキャッシュ対策）
    html = must_sub(r'<meta name=viewport content="[^"]*">', lambda m_: VIEWPORT_META + head, html, what="viewport")
    html = html.replace("<html><head>", '<html lang="ja" class="vpwait"><head><style>html.vpwait{visibility:hidden;animation:vpshow 0s 1.2s forwards}@keyframes vpshow{to{visibility:visible}}</style>', 1)
    return html


VIEWPORT_META = '<meta name="viewport" content="width=device-width,initial-scale=1,minimum-scale=1,maximum-scale=1,user-scalable=no,viewport-fit=cover">'


def load_voices(app):
    """tools/voices/<app>.json を読み、音声ファイルがそろっているか確かめる。"""
    p = os.path.join(TOOLS, "voices", f"{app}.json")
    if not os.path.exists(p):
        return {}
    vs = json.load(open(p, encoding="utf-8"))
    for v, recs in vs.items():
        if v not in VOICE_INFO:
            sys.exit(f"build: 声 {v} が VOICE_INFO にありません")
        for rk, (f, h, st) in recs.items():
            if not os.path.exists(os.path.join(ROOT, app, "voice", v, f)):
                sys.exit(f"build: {app}/voice/{v}/{f} がありません")
    return vs


VOICE_JS = r"""/*VOICE1*/
// 録音の声（VOICEVOX。オフライン版だけ）：設定の「読み上げの声」で選んだ声の目録を使う。ファイルは暗号化してある
const VREC=__VREC__;
const VCACHE="riron-__APP__-voice";
const REC=new Proxy({},{get:(_,k)=>{ const v=VREC.v[setting("tts")]; const r=v&&typeof k==="string"&&v.r[k]; return r?{f:setting("tts")+"/"+r[0],h:r[1],st:r[2]}:undefined; }});
let vKeyP=null;
function vKey(){ if(!vKeyP){ vKeyP=(async()=>{ const s=localStorage.getItem("riron-offline-key"); if(!s) throw new Error("key");
    const b=Uint8Array.from(atob(s),c=>c.charCodeAt(0)); return crypto.subtle.importKey("pkcs8",b,{name:"RSA-OAEP",hash:"SHA-256"},false,["decrypt"]); })();
  vKeyP.catch(()=>{ vKeyP=null; }); } return vKeyP; }
async function recDecrypt(ab){
  const u=new Uint8Array(ab);
  if(u.length<20||String.fromCharCode(u[0],u[1],u[2],u[3])!=="RIA1") throw new Error("format");
  const n=(u[4]<<8)|u[5];
  const raw=await crypto.subtle.decrypt({name:"RSA-OAEP"},await vKey(),u.subarray(6,6+n));
  const cek=await crypto.subtle.importKey("raw",raw,"AES-GCM",false,["decrypt"]);
  const pt=await crypto.subtle.decrypt({name:"AES-GCM",iv:u.subarray(6+n,18+n)},cek,u.subarray(18+n));
  return new Blob([pt],{type:"audio/mp4"});
}
// 「この端末に保存」：選んだ声のファイルを全部、端末の保存場所（VCACHE）に入れる。使わなくなったファイルは消す
const vSave={k:"",run:false,n:-1,tot:0,err:0};
function vFiles(k){ const v=VREC.v[k]; return v?Object.values(v.r).map(r=>REC_DIR+k+"/"+r[0]):[]; }
function vMB(k){ const v=VREC.v[k]; return v?Math.max(1,Math.round(v.mb)):0; }
function vPaint(){ const el=document.querySelector("#vsave-st"), b=document.querySelector("#vsave-go"); const k=setting("tts");
  if(!el) return;
  if(!window.caches){ el.textContent="この端末では保存できません。"; if(b) b.hidden=true; return; }
  if(vSave.k!==k||vSave.n<0){ el.textContent="確認しています…"; return; }
  if(vSave.run){ el.textContent=`保存しています… ${vSave.n} / ${vSave.tot}`; if(b){ b.disabled=true; b.textContent="保存中"; } return; }
  if(vSave.n>=vSave.tot){ el.textContent=`保存済みです（${vSave.tot}件・約${vMB(k)}MB）。通信がなくても、この声で聞けます。`; if(b) b.hidden=true; return; }
  el.textContent=(vSave.err?`保存できなかったファイルがあります（${vSave.err}件）。通信できる場所で、もう一度押してください。`:"")+`${vSave.n} / ${vSave.tot}件を保存済み（全部で約${vMB(k)}MB）。保存すると、通信がなくてもこの声で聞けます。`;
  if(b){ b.hidden=false; b.disabled=false; b.textContent="保存する"; } }
async function vCheck(k){
  if(!window.caches||!VREC.v[k]) return;
  const c=await caches.open(VCACHE); const keys=await c.keys();
  const all=new Set(Object.keys(VREC.v).flatMap(vFiles).map(f=>f.split("voice/")[1]));
  // 今の目録にないファイル（作り直す前の古い音声）は消す
  for(const r of keys){ const p=new URL(r.url).pathname.split("/voice/")[1]; if(p&&!all.has(p)) c.delete(r); }
  const have=new Set(keys.map(r=>new URL(r.url).pathname.split("/voice/")[1]));
  if(vSave.run&&vSave.k===k) return;
  vSave.k=k; vSave.tot=vFiles(k).length; vSave.n=vFiles(k).filter(f=>have.has(f.split("voice/")[1])).length; vPaint();
}
async function vSaveStart(k){
  if(vSave.run||!window.caches||!VREC.v[k]) return;
  try{ if(navigator.storage&&navigator.storage.persist) navigator.storage.persist(); }catch(e){}
  const c=await caches.open(VCACHE); const have=new Set((await c.keys()).map(r=>new URL(r.url).pathname));
  const fs=vFiles(k); vSave.k=k; vSave.run=true; vSave.tot=fs.length; vSave.err=0; vSave.n=0; vPaint();
  for(const f of fs){
    const url=new URL(f,location.href);
    if(!have.has(url.pathname)){ try{ const r=await fetch(url,{cache:"reload"}); if(!r.ok) throw new Error(r.status); await c.put(url,r); }catch(e){ vSave.err++; vSave.n--; } }
    vSave.n++; if(vSave.n%5===0) vPaint();
  }
  vSave.run=false; vSave.n=Math.max(0,vSave.n); await vCheck(k); vPaint();
}
function vSaveLabel(){ setTimeout(()=>vCheck(setting("tts")).catch(()=>{}),0); return "確認しています…"; }
document.addEventListener("click",e=>{ const b=e.target&&e.target.closest&&e.target.closest("#vsave-go"); if(b) vSaveStart(setting("tts")).catch(()=>{ vSave.run=false; vPaint(); }); });
/*VOICE1-END*/"""


def voice_patch(html, app):
    vs = load_voices(app)
    if not vs:
        return html
    order = [v for v in VOICE_INFO if v in vs]
    mb = {}
    for v in order:
        tot = sum(os.path.getsize(os.path.join(ROOT, app, "voice", v, f)) for f, _, _ in vs[v].values())
        mb[v] = round(tot / 1e6, 1)
    vrec = {"v": {v: {"name": VOICE_INFO[v][0], "mb": mb[v], "r": vs[v]} for v in order}}
    js = VOICE_JS.replace("__VREC__", json.dumps(vrec, ensure_ascii=False, separators=(",", ":"))).replace("__APP__", app)
    # 目録（REC）を、選んだ声の目録に置きかえる（入れ済みなら差し替える）
    if "/*VOICE1*/" in html:
        html = must_sub(r"/\*VOICE1\*/.*?/\*VOICE1-END\*/", lambda m: js, html, flags=re.S, what="VOICE1 の範囲")
    else:
        html = must_sub(r"^const REC=\{.*\};?$", lambda m: js, html, flags=re.M, what="const REC（録音の声）")
    # 音声ファイルは暗号化してあるので、読み込んだら復号してから鳴らす
    if "then(recDecrypt)" not in html:
      html = must_sub(re.escape('const pr=fetch(url).then(r=>{ if(!r.ok) throw new Error(r.status); return r.blob(); }).then(b=>URL.createObjectURL(b));'),
                    lambda m: 'const pr=fetch(url).then(r=>{ if(!r.ok) throw new Error(r.status); return r.arrayBuffer(); }).then(recDecrypt).then(b=>URL.createObjectURL(b));',
                      html, what="recBlob（復号）")
    # 設定の「音声」に、声の選択と「この端末に保存」を出す
    credit = "、".join(VOICE_INFO[v][1] for v in order)
    choices = json.dumps([["device", "端末の音声"]] + [[v, VOICE_INFO[v][0]] for v in order], ensure_ascii=False)
    rows = ('    (TTS_OK?row("読み上げの声","暗記の本文と規定の名前を、あらかじめ作った自然な声で読みます（ほかの形式と、あとから文を直した問題は端末の声）。「端末の音声」はこの端末の声で読みます。音声：' + credit + '",opt("tts",' + choices + '))'
            '+(VREC.v[setting("tts")]?row("この声を端末に保存",`<span id="vsave-st">${vSaveLabel()}</span>`,`<button class="btn" id="vsave-go" hidden>保存する</button>`):""):"")+\n')
    if 'row("読み上げの声"' in html:
        html = must_sub(r'    \(TTS_OK\?row\("読み上げの声".*\n', lambda m: rows, html, what="設定の音声（読み上げの声・差し替え）")
    else:
        html = must_sub(r'const secM=sec\("読み上げ・効果音",\n', lambda m: m.group(0) + rows, html, what="設定の音声（読み上げの声）")
    return html


def encrypt(plain_bytes):
    pub = serialization.load_pem_public_key(open(os.path.join(TOOLS, "pubkey.pem"), "rb").read())
    cek = os.urandom(32)
    iv = os.urandom(12)
    ct = AESGCM(cek).encrypt(iv, gzip.compress(plain_bytes, 9, mtime=0), None)
    wrapped = pub.encrypt(cek, padding.OAEP(mgf=padding.MGF1(hashes.SHA256()), algorithm=hashes.SHA256(), label=None))
    return b"RIR1" + len(wrapped).to_bytes(2, "big") + wrapped + iv + ct


LOADER = r"""<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,minimum-scale=1,maximum-scale=1,user-scalable=no,viewport-fit=cover">
<title>__NAME__</title>
<link rel="manifest" href="manifest.webmanifest">
<link rel="apple-touch-icon" href="icon3-180.png">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-title" content="__SHORT__">
<meta name="theme-color" content="__LIGHT__" media="(prefers-color-scheme: light)">
<meta name="theme-color" content="__DARK__" media="(prefers-color-scheme: dark)">
<script>
/* アプリの「画面の色」でライト／ダークを選んでいるときは、端末の設定ではなく、その色を上部の帯に使う。
   端末は起動したときに読んだ色で帯を塗るため、アプリが開く前（ここ）で決めておく */
(function(){try{
  var s=JSON.parse(localStorage.getItem("__KEY__")||"null"), t=s&&s.settings&&s.settings.theme;
  if(t==="light"||t==="dark"){
    document.documentElement.setAttribute("data-theme",t);
    var old=document.querySelectorAll('meta[name="theme-color"]');
    for(var i=0;i<old.length;i++) old[i].parentNode.removeChild(old[i]);
    var m=document.createElement("meta"); m.setAttribute("name","theme-color");
    m.setAttribute("content",t==="light"?"__LIGHT__":"__DARK__"); document.head.appendChild(m);
  }
}catch(e){}})();
</script>
<style>
:root{--bg:#D2CAB8;--surface:#FFFFFD;--ink:#191D17;--muted:#5A5F52;--line:#D1CABA;--accent:#28A000;--on-accent:#FFFFFF;--bad:#A4531D;color-scheme:light}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--bg:#0F141B;--surface:#171E28;--ink:#E7ECF3;--muted:#9AA6B6;--line:#2A3441;--accent:#8DB2E0;--on-accent:#0F141B;--bad:#E4A266;color-scheme:dark}}
:root[data-theme="dark"]{--bg:#0F141B;--surface:#171E28;--ink:#E7ECF3;--muted:#9AA6B6;--line:#2A3441;--accent:#8DB2E0;--on-accent:#0F141B;--bad:#E4A266;color-scheme:dark}
*{box-sizing:border-box}
html,body{margin:0;min-height:100%;background:var(--bg);color:var(--ink);font-family:"Hiragino Sans","Hiragino Kaku Gothic ProN","Yu Gothic",sans-serif;-webkit-text-size-adjust:100%}
body{display:grid;place-items:center;min-height:100vh;padding:max(24px,env(safe-area-inset-top)) 16px max(24px,env(safe-area-inset-bottom))}
.card{width:100%;max-width:380px;background:var(--surface);border:1px solid var(--line);border-radius:18px;padding:28px 22px 24px;display:grid;gap:14px;text-align:center;box-shadow:0 1px 3px rgba(20,34,54,.06),0 8px 24px -10px rgba(20,34,54,.18)}
.ic{width:72px;height:72px;border-radius:16px;justify-self:center}
h1{font-family:"Hiragino Mincho ProN","Yu Mincho",serif;font-size:22px;margin:0;letter-spacing:.04em}
p{margin:0;font-size:14px;line-height:1.7;color:var(--muted)}
.spin{width:28px;height:28px;border-radius:50%;border:3px solid var(--line);border-top-color:var(--accent);justify-self:center;animation:sp 0.9s linear infinite}
@keyframes sp{to{transform:rotate(360deg)}}
@media (prefers-reduced-motion: reduce){.spin{animation:none}}
form{display:grid;gap:10px;text-align:left}
label{font-size:13px;font-weight:700}
input{font:inherit;font-size:17px;letter-spacing:.08em;color:var(--ink);background:var(--bg);border:1px solid var(--line);border-radius:12px;padding:11px 14px;width:100%}
input:focus-visible{outline:2px solid var(--accent);outline-offset:1px}
button{font:inherit;font-size:16px;font-weight:700;border:0;border-radius:12px;padding:12px;background:var(--accent);color:var(--on-accent);cursor:pointer}
button:disabled{opacity:.6}
.err{color:var(--bad);font-size:13px;min-height:1.2em;margin:0}
.hint{font-size:13px;text-align:left;background:var(--bg);border-radius:12px;padding:10px 12px}
[hidden]{display:none!important}
</style>
</head>
<body>
<main class="card" id="boot">
  <img class="ic" src="icon3-180.png" alt="">
  <h1>__NAME__</h1>
  <div id="s-load"><div class="spin" aria-hidden="true"></div><p style="margin-top:10px">読み込み中…</p></div>
  <form id="s-lock" hidden autocomplete="on">
    <p>この端末で初めて開くときだけ、パスワードを入れてください。</p>
    <label for="pw">パスワード</label>
    <input id="pw" name="password" type="password" autocomplete="current-password" autocapitalize="none" autocorrect="off" spellcheck="false" inputmode="text" required>
    <p class="err" id="pw-err" role="alert"></p>
    <button type="submit" id="pw-go">開く</button>
  </form>
  <p class="err" id="s-err" hidden role="alert"></p>
  <p class="hint" id="s-home" hidden>ホーム画面に追加すると、通信がなくても開けます。Safariの共有ボタン（□に↑）→「ホーム画面に追加」を押し、追加したアイコンから開いてください。</p>
</main>
<script>
(()=>{
  "use strict";
  const LS_KEY="riron-offline-key";
  const $=id=>document.getElementById(id);
  const b64d=s=>Uint8Array.from(atob(s),c=>c.charCodeAt(0));
  const b64e=buf=>{const a=new Uint8Array(buf);let s="";for(let i=0;i<a.length;i+=0x8000)s+=String.fromCharCode.apply(null,a.subarray(i,i+0x8000));return btoa(s);};
  const standalone=navigator.standalone===true||(window.matchMedia&&matchMedia("(display-mode: standalone)").matches);
  const ios=/iP(hone|ad|od)/.test(navigator.userAgent)||(navigator.platform==="MacIntel"&&navigator.maxTouchPoints>1);
  let hadController=false, opened=false;

  function show(which,msg){
    $("s-load").hidden=which!=="load"; $("s-lock").hidden=which!=="lock"; $("s-err").hidden=which!=="err";
    if(which==="err") $("s-err").textContent=msg||"";
    $("s-home").hidden=!(ios&&!standalone&&which!=="load");
    if(which==="lock") setTimeout(()=>{ try{$("pw").focus();}catch(e){} },50);
  }
  function setSync(t){ const s=document.getElementById("sync"); if(s) s.textContent=t; }

  // 新しい版が届いたら、アプリの下に知らせる（入力中の答えが消えないよう、自動では読み込み直さない）
  function showUpdate(){
    if(!opened||document.getElementById("riron-upd")) return;
    const d=document.createElement("div"); d.id="riron-upd";
    d.setAttribute("role","status");
    d.style.cssText="position:fixed;left:0;right:0;margin:0 auto;width:max-content;bottom:calc(16px + env(safe-area-inset-bottom,0px));z-index:60;display:flex;gap:10px;align-items:center;background:var(--ink,#18212E);color:var(--surface,#fff);padding:10px 12px 10px 16px;border-radius:12px;font-size:14px;font-weight:700;box-shadow:0 10px 30px -10px rgba(0,0,0,.45);max-width:calc(100% - 32px)";
    d.innerHTML='<span style="white-space:nowrap">新しい版があります</span><button type="button" style="white-space:nowrap;font:inherit;font-size:13px;border:0;border-radius:8px;padding:6px 12px;background:var(--surface,#fff);color:var(--ink,#18212E);font-weight:700">読み込み直す</button><button type="button" aria-label="閉じる" style="font:inherit;font-size:16px;border:0;background:transparent;color:inherit;padding:2px 6px">×</button>';
    const [go,x]=d.querySelectorAll("button"); go.onclick=()=>location.reload(); x.onclick=()=>d.remove();
    document.body.appendChild(d);
  }

  if("serviceWorker" in navigator){
    hadController=!!navigator.serviceWorker.controller;
    navigator.serviceWorker.addEventListener("controllerchange",()=>{ if(hadController) showUpdate(); hadController=true; });
    navigator.serviceWorker.register("sw.js").catch(()=>{});
  }

  async function storedKey(){
    let s=null; try{ s=localStorage.getItem(LS_KEY); }catch(e){}
    if(!s) return null;
    try{ return await crypto.subtle.importKey("pkcs8",b64d(s),{name:"RSA-OAEP",hash:"SHA-256"},false,["decrypt"]); }
    catch(e){ return null; }
  }
  function normPass(p){ return p.normalize("NFKC").toLowerCase().replace(/[\s\-ー－‐―]/g,""); }
  async function unlock(pass){
    const r=await fetch("key.json"); if(!r.ok) throw new Error("net");
    const kj=await r.json();
    const base=await crypto.subtle.importKey("raw",new TextEncoder().encode(normPass(pass)),"PBKDF2",false,["deriveKey"]);
    const kek=await crypto.subtle.deriveKey({name:"PBKDF2",salt:b64d(kj.salt),iterations:kj.iter,hash:"SHA-256"},base,{name:"AES-GCM",length:256},false,["decrypt"]);
    let pk;
    try{ pk=await crypto.subtle.decrypt({name:"AES-GCM",iv:b64d(kj.iv)},kek,b64d(kj.data)); }
    catch(e){ throw new Error("pass"); }
    try{ localStorage.setItem(LS_KEY,b64e(pk)); }catch(e){}
    return crypto.subtle.importKey("pkcs8",pk,{name:"RSA-OAEP",hash:"SHA-256"},false,["decrypt"]);
  }
  async function decryptApp(key){
    let res;
    try{ res=await fetch("app.bin"); }catch(e){ throw new Error("net"); }
    if(!res.ok) throw new Error("net");
    const buf=new Uint8Array(await res.arrayBuffer());
    if(buf.length<20||String.fromCharCode(buf[0],buf[1],buf[2],buf[3])!=="RIR1") throw new Error("format");
    const n=(buf[4]<<8)|buf[5];
    const wrapped=buf.slice(6,6+n), iv=buf.slice(6+n,18+n), ct=buf.slice(18+n);
    let raw;
    try{ raw=await crypto.subtle.decrypt({name:"RSA-OAEP"},key,wrapped); }catch(e){ throw new Error("key"); }
    const cek=await crypto.subtle.importKey("raw",raw,"AES-GCM",false,["decrypt"]);
    const gz=await crypto.subtle.decrypt({name:"AES-GCM",iv},cek,ct);
    if(typeof DecompressionStream==="undefined") throw new Error("old");
    return await new Response(new Blob([gz]).stream().pipeThrough(new DecompressionStream("gzip"))).text();
  }
  function openHtml(html){
    opened=true;
    document.open(); document.write(html); document.close();
    // オフライン用の保存が済んだかを、アプリの見出しの下に出す
    if("serviceWorker" in navigator&&window.caches){
      navigator.serviceWorker.ready.then(()=>caches.keys()).then(ks=>Promise.all(ks.map(k=>caches.open(k).then(c=>c.match("app.bin"))))).then(ms=>{
        setSync(ms.some(Boolean)?"":"オフライン用に保存できていません。通信できる場所で開き直してください");
      }).catch(()=>setSync(""));
    } else setSync("この端末ではオフライン用に保存できません");
  }
  function fail(e){
    const m=e&&e.message;
    if(m==="net") show("err","読み込めませんでした。最初の1回は通信できる場所で開いてください。");
    else if(m==="old") show("err","このiOSでは開けません。iOSを最新にしてから開いてください。");
    else show("err","開けませんでした。時間をおいて開き直してください。");
  }
  async function start(){
    show("load");
    const key=await storedKey();
    if(!key){ show("lock"); return; }
    try{ openHtml(await decryptApp(key)); }
    catch(e){
      if(e&&e.message==="key"){ try{ localStorage.removeItem(LS_KEY); }catch(_){} show("lock"); return; }
      fail(e);
    }
  }
  $("s-lock").addEventListener("submit",async ev=>{
    ev.preventDefault();
    const pw=$("pw").value; if(!pw.trim()) return;
    $("pw-go").disabled=true; $("pw-err").textContent="";
    try{
      const key=await unlock(pw);
      show("load");
      openHtml(await decryptApp(key));
    }catch(e){
      $("pw-go").disabled=false;
      if(e&&e.message==="pass"){ $("pw-err").textContent="パスワードが違います。"; $("pw").select(); }
      else fail(e);
    }
  });
  if(!(window.crypto&&crypto.subtle)){ show("err","この画面はSafariで開いてください。"); return; }
  start();
})();
</script>
</body>
</html>
"""

SW = r"""// オフライン用：アプリのファイルを端末に保存し、通信がなくても開けるようにする
const VERSION="__VERSION__";
const PREFIX="riron-__APP__-";
const CACHE=PREFIX+VERSION;
const VCACHE=PREFIX+"voice";  // 録音の声（版が変わっても残す。古いファイルはアプリの側で消す）
const FILES=["./","index.html","app.bin","key.json","manifest.webmanifest","icon3-180.png","icon3-192.png","icon3-512.png"];
self.addEventListener("install",e=>{
  e.waitUntil(caches.open(CACHE).then(c=>c.addAll(FILES.map(f=>new Request(f,{cache:"reload"})))).then(()=>self.skipWaiting()));
});
self.addEventListener("activate",e=>{
  e.waitUntil(caches.keys().then(ks=>Promise.all(ks.filter(k=>k.startsWith(PREFIX)&&k!==CACHE&&k!==VCACHE).map(k=>caches.delete(k)))).then(()=>self.clients.claim()));
});
self.addEventListener("fetch",e=>{
  const r=e.request;
  if(r.method!=="GET") return;
  const u=new URL(r.url);
  if(u.origin!==location.origin) return;
  if(r.mode==="navigate"){
    e.respondWith(caches.open(CACHE).then(c=>c.match("./")).then(m=>m||fetch(r)).catch(()=>fetch(r)));
    return;
  }
  if(u.pathname.includes("/voice/")){
    e.respondWith(caches.open(VCACHE).then(c=>c.match(r,{ignoreSearch:true}).then(m=>m||fetch(r).then(res=>{ if(res.ok) c.put(r,res.clone()); return res; }))));
    return;
  }
  e.respondWith(caches.open(CACHE).then(c=>c.match(r,{ignoreSearch:true})).then(m=>m||fetch(r)));
});
"""


def build(app, src):
    a = APPS[app]
    out = os.path.join(ROOT, app)
    os.makedirs(out, exist_ok=True)
    html = open(src, encoding="utf-8").read()
    if f'app:"{a["id"]}"' not in html:
        sys.exit(f"build: {src} は {a['name']} のアプリではないようです")
    if 'row("オフライン版"' in html:
        # すでにオフライン用に直したHTML（app.bin を復号したもの）から作り直すとき：声だけ入れ直す
        #   claude.ai 版のHTMLは約10MBあり、作業環境によっては取り出せないため（2026-11-27）
        html = voice_patch(html, app)
    else:
        html = offline_patch(html, app)
    loader =(LOADER.replace("__NAME__", a["name"]).replace("__SHORT__", a["short"]).replace("__KEY__", a["key"])
              .replace("__LIGHT__", a.get("light", THEME_LIGHT)).replace("__DARK__", THEME_DARK))
    ic = a.get("icon", "icon3")
    static = [f.replace("icon3-", ic + "-") for f in STATIC]
    loader = loader.replace("icon3-", ic + "-")
    open(os.path.join(out, "index.html"), "w", encoding="utf-8").write(loader)
    manifest = {
        "name": a["name"], "short_name": a["short"], "lang": "ja",
        "start_url": "./", "scope": "./", "display": "standalone",
        "background_color": a.get("light", THEME_LIGHT), "theme_color": a.get("light", THEME_LIGHT),
        "icons": [{"src": ic + "-192.png", "sizes": "192x192", "type": "image/png"},
                  {"src": ic + "-512.png", "sizes": "512x512", "type": "image/png"}],
    }
    json.dump(manifest, open(os.path.join(out, "manifest.webmanifest"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    shutil.copyfile(os.path.join(TOOLS, "key.json"), os.path.join(out, "key.json"))
    for f in static:
        if not os.path.exists(os.path.join(out, f)):
            sys.exit(f"build: {app}/{f} がありません")
    # 版の番号：本体の中身（暗号化前）と起動用ファイルから決める。中身が変わったときだけ端末に新しい版が届く
    h = hashlib.sha256()
    h.update(html.encode("utf-8"))
    for f in ["index.html", "manifest.webmanifest", "key.json"] + static:
        h.update(open(os.path.join(out, f), "rb").read())
    version = time.strftime("%Y%m%d") + "-" + h.hexdigest()[:10]
    old = open(os.path.join(out, "sw.js"), encoding="utf-8").read() if os.path.exists(os.path.join(out, "sw.js")) else ""
    m = re.search(r'const VERSION="([^"]+)"', old)
    same = m and m.group(1).split("-", 1)[-1] == version.split("-", 1)[-1] and os.path.exists(os.path.join(out, "app.bin"))
    if same:
        version = m.group(1)  # 中身が同じなら、版の番号も app.bin もそのまま（暗号化は毎回結果が変わるため）
    else:
        open(os.path.join(out, "app.bin"), "wb").write(encrypt(html.encode("utf-8")))
    open(os.path.join(out, "sw.js"), "w", encoding="utf-8").write(SW.replace("__VERSION__", version).replace("__APP__", app).replace("icon3-", ic + "-"))
    print(f"{app}: version {version}, app.bin {os.path.getsize(os.path.join(out, 'app.bin')):,} bytes")


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] not in APPS:
        sys.exit(__doc__)
    build(sys.argv[1], sys.argv[2])

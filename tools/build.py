#!/usr/bin/env python3
"""理論アプリのオフライン版（ホーム画面に追加して使うWebアプリ）を作る。

使い方:
    python3 tools/build.py sozoku  path/to/相続税アプリ.html
    python3 tools/build.py shohi   path/to/消費税アプリ.html

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
    "sozoku": {"name": "相続税 理論", "short": "相続税", "id": "sozoku-riron"},
    "shohi": {"name": "消費税 理論", "short": "消費税", "id": "shohi-riron"},
}
THEME_LIGHT, THEME_DARK = "#EEF1F5", "#0F141B"
STATIC = ["icon-180.png", "icon-192.png", "icon-512.png"]


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
    html = must_sub(r"^const REC=\{.*\};?$", "const REC={};", html, flags=re.M, what="const REC")
    html = must_sub(r'row\("読み上げの音声",.*?opt\("tts",\[\["rec","自然な音声"\],\["device","端末の音声"\]\]\)\)\+', "", html, what="読み上げの音声の設定")
    html = must_sub(r'tts:"rec"', 'tts:"device"', html, what="tts の初期値")
    html = html.replace("「端末の音声」を選んだときに使う声です。", "読み上げに使う声です。")
    # 3) オフライン版であることを表示する（起動用ページが準備の状況に合わせて書き換える）
    html = must_sub(r'<span class="sync" id="sync"></span>', '<span class="sync" id="sync">オフライン版</span>', html, what="sync 表示")
    html = must_sub(r'const secC=sec\("記録の管理",\n', 'const secC=sec("記録の管理",\n    row("オフライン版","通信がなくても使えるよう、この端末に保存しているアプリです。記録はこの端末だけに保存されます。claude.ai版と記録を移すときは、下の「記録の書き出し」と「記録の読み込み」を使います。","")+\n', html, what="記録の管理")
    # 4) ホーム画面に追加したときの名前・アイコン
    head = (
        '<link rel="manifest" href="manifest.webmanifest">'
        '<link rel="apple-touch-icon" href="icon-180.png">'
        '<meta name="apple-mobile-web-app-capable" content="yes">'
        '<meta name="mobile-web-app-capable" content="yes">'
        f'<meta name="apple-mobile-web-app-title" content="{a["short"]}">'
        '<meta name="apple-mobile-web-app-status-bar-style" content="default">'
        f'<meta name="theme-color" content="{THEME_LIGHT}" media="(prefers-color-scheme: light)">'
        f'<meta name="theme-color" content="{THEME_DARK}" media="(prefers-color-scheme: dark)">'
    )
    html = must_sub(r'(<meta name=viewport content="width=device-width,initial-scale=1,viewport-fit=cover">)', r"\1" + head, html, what="viewport")
    html = html.replace("<html><head>", '<html lang="ja"><head>', 1)
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
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>__NAME__</title>
<link rel="manifest" href="manifest.webmanifest">
<link rel="apple-touch-icon" href="icon-180.png">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-title" content="__SHORT__">
<meta name="apple-mobile-web-app-status-bar-style" content="default">
<meta name="theme-color" content="__LIGHT__" media="(prefers-color-scheme: light)">
<meta name="theme-color" content="__DARK__" media="(prefers-color-scheme: dark)">
<style>
:root{--bg:#EEF1F5;--surface:#FFFFFF;--ink:#18212E;--muted:#5F6B7B;--line:#DEE3EA;--accent:#23456F;--on-accent:#FFFFFF;--bad:#A4531D;color-scheme:light}
@media (prefers-color-scheme: dark){:root{--bg:#0F141B;--surface:#171E28;--ink:#E7ECF3;--muted:#9AA6B6;--line:#2A3441;--accent:#8DB2E0;--on-accent:#0F141B;--bad:#E4A266;color-scheme:dark}}
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
  <img class="ic" src="icon-180.png" alt="">
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
      setSync("オフライン版：この端末に保存しています…");
      navigator.serviceWorker.ready.then(()=>caches.keys()).then(ks=>Promise.all(ks.map(k=>caches.open(k).then(c=>c.match("app.bin"))))).then(ms=>{
        setSync(ms.some(Boolean)?"オフライン版（記録はこの端末に保存）":"オフライン版：保存できていません。通信できる場所で開き直してください");
      }).catch(()=>setSync("オフライン版（記録はこの端末に保存）"));
    } else setSync("オフライン版：この端末ではオフライン用に保存できません");
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
const FILES=["./","index.html","app.bin","key.json","manifest.webmanifest","icon-180.png","icon-192.png","icon-512.png"];
self.addEventListener("install",e=>{
  e.waitUntil(caches.open(CACHE).then(c=>c.addAll(FILES.map(f=>new Request(f,{cache:"reload"})))).then(()=>self.skipWaiting()));
});
self.addEventListener("activate",e=>{
  e.waitUntil(caches.keys().then(ks=>Promise.all(ks.filter(k=>k.startsWith(PREFIX)&&k!==CACHE).map(k=>caches.delete(k)))).then(()=>self.clients.claim()));
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
    html = offline_patch(html, app)
    loader =(LOADER.replace("__NAME__", a["name"]).replace("__SHORT__", a["short"])
              .replace("__LIGHT__", THEME_LIGHT).replace("__DARK__", THEME_DARK))
    open(os.path.join(out, "index.html"), "w", encoding="utf-8").write(loader)
    manifest = {
        "name": a["name"], "short_name": a["short"], "lang": "ja",
        "start_url": "./", "scope": "./", "display": "standalone",
        "background_color": THEME_LIGHT, "theme_color": THEME_LIGHT,
        "icons": [{"src": "icon-192.png", "sizes": "192x192", "type": "image/png"},
                  {"src": "icon-512.png", "sizes": "512x512", "type": "image/png"}],
    }
    json.dump(manifest, open(os.path.join(out, "manifest.webmanifest"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    shutil.copyfile(os.path.join(TOOLS, "key.json"), os.path.join(out, "key.json"))
    for f in STATIC:
        if not os.path.exists(os.path.join(out, f)):
            sys.exit(f"build: {app}/{f} がありません")
    # 版の番号：本体の中身（暗号化前）と起動用ファイルから決める。中身が変わったときだけ端末に新しい版が届く
    h = hashlib.sha256()
    h.update(html.encode("utf-8"))
    for f in ["index.html", "manifest.webmanifest", "key.json"] + STATIC:
        h.update(open(os.path.join(out, f), "rb").read())
    version = time.strftime("%Y%m%d") + "-" + h.hexdigest()[:10]
    old = open(os.path.join(out, "sw.js"), encoding="utf-8").read() if os.path.exists(os.path.join(out, "sw.js")) else ""
    m = re.search(r'const VERSION="([^"]+)"', old)
    same = m and m.group(1).split("-", 1)[-1] == version.split("-", 1)[-1] and os.path.exists(os.path.join(out, "app.bin"))
    if same:
        version = m.group(1)  # 中身が同じなら、版の番号も app.bin もそのまま（暗号化は毎回結果が変わるため）
    else:
        open(os.path.join(out, "app.bin"), "wb").write(encrypt(html.encode("utf-8")))
    open(os.path.join(out, "sw.js"), "w", encoding="utf-8").write(SW.replace("__VERSION__", version).replace("__APP__", app))
    print(f"{app}: version {version}, app.bin {os.path.getsize(os.path.join(out, 'app.bin')):,} bytes")


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] not in APPS:
        sys.exit(__doc__)
    build(sys.argv[1], sys.argv[2])

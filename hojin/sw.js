// オフライン用：アプリのファイルを端末に保存し、通信がなくても開けるようにする
const VERSION="20261127-e71596b3ec";
const PREFIX="riron-hojin-";
const CACHE=PREFIX+VERSION;
const VCACHE=PREFIX+"voice";  // 録音の声（版が変わっても残す。古いファイルはアプリの側で消す）
const FILES=["./","index.html","app.bin","key.json","manifest.webmanifest","icon4-180.png","icon4-192.png","icon4-512.png"];
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

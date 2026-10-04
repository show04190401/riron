// オフライン用：アプリのファイルを端末に保存し、通信がなくても開けるようにする
const VERSION="20261004-87179a0301";
const PREFIX="riron-sozoku-";
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

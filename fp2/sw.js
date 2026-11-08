// FP2級アプリ：オフライン用（版 fa5ab2dc47）
const CACHE="fp2-fa5ab2dc47";
const FILES=["./","index.html","manifest.webmanifest","icon-180.png","icon-192.png","icon-512.png"];
self.addEventListener("install",e=>{e.waitUntil(caches.open(CACHE).then(c=>c.addAll(FILES)));});
self.addEventListener("activate",e=>{e.waitUntil(caches.keys().then(ks=>Promise.all(ks.filter(k=>k.startsWith("fp2-")&&k!==CACHE).map(k=>caches.delete(k)))).then(()=>self.clients.claim()));});
self.addEventListener("message",e=>{ if(e.data==="skip") self.skipWaiting(); });
self.addEventListener("fetch",e=>{
  const u=new URL(e.request.url);
  if(e.request.method!=="GET") return;
  // 文字（Google Fonts）は、一度読めたら端末に残す
  if(u.host.endsWith("fonts.googleapis.com")||u.host.endsWith("fonts.gstatic.com")){
    e.respondWith(caches.open(CACHE+"-font").then(c=>c.match(e.request).then(r=>r||fetch(e.request).then(res=>{c.put(e.request,res.clone());return res;}).catch(()=>r))));
    return;
  }
  if(u.origin!==location.origin) return;
  // ページは「通信できれば新しい版、できなければ保存した版」
  if(e.request.mode==="navigate"){
    e.respondWith(fetch(e.request).then(res=>{const cp=res.clone();caches.open(CACHE).then(c=>c.put("index.html",cp));return res;}).catch(()=>caches.match("index.html")));
    return;
  }
  e.respondWith(caches.match(e.request).then(r=>r||fetch(e.request)));
});

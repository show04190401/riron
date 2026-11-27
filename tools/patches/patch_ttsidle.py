"""読み上げ中の操作の帯（速さ・連続・停止）を、3秒さわらなければ下へしまう（2026-11-27 ユーザーの要望）。
画面のどこかにさわると、また出す。何度実行しても同じ結果。使い方: python3 patch_ttsidle.py <html>..."""
import sys
JS_AFTER = 'setPidBtn=(o=>function(pid,on){ o(pid,on); setTimeout(ttsBarSync,0); })(setPidBtn);\n'
JS = '''/*TTSIDLE*/
// 読み上げ中の操作の帯は、3秒さわらなければ下へしまう。画面のどこかにさわると、また出す（2026-11-27 ユーザーの要望）
let TTSB_IDLE=0;
function ttsBarWake(){ const b=document.getElementById("ttsbar"); if(!b||b.hidden) return; b.classList.remove("away"); clearTimeout(TTSB_IDLE); TTSB_IDLE=setTimeout(()=>{ if(!b.hidden) b.classList.add("away"); },3000); }
["pointerdown","touchstart","keydown","wheel"].forEach(t=>document.addEventListener(t,ttsBarWake,{capture:true,passive:true}));
ttsBarSync=(o=>function(){ const b0=document.getElementById("ttsbar"), was=!!(b0&&!b0.hidden); o(); const b=document.getElementById("ttsbar"); if(b&&!b.hidden&&!was) ttsBarWake(); })(ttsBarSync);
/*TTSIDLE-END*/
'''
CSS_AFTER = 'body.ttson{padding-bottom:120px}\n'
CSS = '''/*TTSIDLECSS*/.ttsbar{transition:transform .28s ease,opacity .28s ease}.ttsbar.away{transform:translate(-50%,calc(100% + 28px));opacity:0;pointer-events:none}/*TTSIDLECSS-END*/
'''
for p in sys.argv[1:]:
    h = open(p, encoding="utf-8").read()
    if "/*TTSIDLE*/" in h:
        print(p, "入れ済み"); continue
    assert h.count(JS_AFTER) == 1 and h.count(CSS_AFTER) == 1, p
    h = h.replace(JS_AFTER, JS_AFTER + JS).replace(CSS_AFTER, CSS_AFTER + CSS)
    open(p, "w", encoding="utf-8").write(h); print(p, "ok")

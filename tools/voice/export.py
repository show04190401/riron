#!/usr/bin/env python3
"""作った音声を、オフライン版の置き場所に移す（tools/voices/<app>.json と <app>/voice/<声>/）。

使い方: python3 tools/voice/export.py <app> <声> <gen.py の出力フォルダ> <segs.json>
  segs.json（いまのアプリの区切り）とハッシュが合う音声だけを入れる。合わないもの（文を直した問題）は入れず、
  その問題は端末の声で読まれる。目録にない古いファイルは <app>/voice/<声>/ から消す。
"""
import json, os, shutil, sys
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
app, v, src, segp = sys.argv[1:5]
segs = {x["rk"]: "".join(s["h"] for s in x["segs"]) for x in json.load(open(segp, encoding="utf-8"))}
recs = {}
for line in open(os.path.join(src, "rec.jsonl"), encoding="utf-8"):
    r = json.loads(line)
    if segs.get(r["rk"]) == r["h"]:
        recs[r["rk"]] = r  # 後に書いた行（作り直した分）を残す
dst = os.path.join(ROOT, app, "voice", v)
os.makedirs(dst, exist_ok=True)
keep = set()
for r in recs.values():
    f = r["f"].split("/", 1)[1]
    keep.add(f)
    if not os.path.exists(os.path.join(dst, f)):
        shutil.copyfile(os.path.join(src, f), os.path.join(dst, f))
for f in os.listdir(dst):
    if f not in keep:
        os.remove(os.path.join(dst, f))
mp = os.path.join(ROOT, "tools", "voices", f"{app}.json")
os.makedirs(os.path.dirname(mp), exist_ok=True)
allv = json.load(open(mp, encoding="utf-8")) if os.path.exists(mp) else {}
allv[v] = {rk: [r["f"].split("/", 1)[1], r["h"], r["st"]] for rk, r in sorted(recs.items())}
json.dump(allv, open(mp, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
print(f"{app}/{v}: {len(recs)} / {len(segs)} 件（{sum(os.path.getsize(os.path.join(dst, f)) for f in keep)/1e6:.1f}MB）")

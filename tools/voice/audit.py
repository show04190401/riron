"""区切りの文（読み間違いの手直しのあと）を形態素に分け、読みを書き出す。
使い方: python -I audit.py <app>  → <app>.readings.txt（語=読み:回数）と、読みが2つ以上ある語の例を表示"""
import json, collections, re, sys, os, pyopenjtalk
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from yomi import fix
app = sys.argv[1]
items = json.load(open(f"{app}.segs.json"))
rd = collections.defaultdict(collections.Counter); ctx = collections.defaultdict(list)
for it in items:
    for s in it["segs"]:
        nodes = pyopenjtalk.run_frontend(fix(app, s["t"]))
        for i, n in enumerate(nodes):
            w = n["string"]
            if re.search(r"[一-龥々]", w):
                p = n["pron"].replace("’", ""); rd[w][p] += 1
                if len(ctx[(w, p)]) < 2: ctx[(w, p)].append("".join(x["string"] for x in nodes[max(0, i-4):i+4]))
open(f"{app}.readings.txt", "w").write("\n".join(f"{w}={'/'.join(c)}:{sum(c.values())}" for w, c in sorted(rd.items(), key=lambda x: -sum(x[1].values()))))
for w, c in sorted(rd.items(), key=lambda x: -sum(x[1].values())):
    if len(c) > 1:
        print(w, " | ".join(f"{p}×{k}〔{ctx[(w,p)][0]}〕" for p, k in c.most_common()))

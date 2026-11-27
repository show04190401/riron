import json, re, sys, os, pyopenjtalk
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from yomi import fix
app = sys.argv[1]; want = dict(x.split("@") if "@" in x else (x, "") for x in sys.argv[2:])
items = json.load(open(f"{app}.segs.json")); seen = {}
for it in items:
    for s in it["segs"]:
        nodes = pyopenjtalk.run_frontend(fix(app, s["t"]))
        for i, n in enumerate(nodes):
            w = n["string"]; p = n["pron"].replace("’", "")
            if w in want and (not want[w] or want[w] == p):
                k = (w, p); seen.setdefault(k, [])
                if len(seen[k]) < 3: seen[k].append("".join(x["string"] for x in nodes[max(0, i-4):i+4]))
for k, v in seen.items(): print(k, v)

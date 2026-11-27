"""設定の「端末の声の種類」の行を消す（2026-11-27 ユーザーの要望「ここは不要です」）。
声は今までどおり自動（設定に記録があればそれ）で選ぶ。何度実行しても同じ結果。使い方: python3 patch_novoicepick.py <html>..."""
import re, sys
for p in sys.argv[1:]:
    h = open(p, encoding="utf-8").read()
    h2, n = re.subn(r'\n *row\("端末の声の種類".*\n', "\n", h)
    if n == 0:
        print(p, "消し済み"); continue
    assert n == 1, p
    open(p, "w", encoding="utf-8").write(h2); print(p, "ok")

#!/usr/bin/env python3
"""作り直した app.bin が本当に元のHTMLに戻るかを確かめる。

使い方:
    python3 tools/verify_build.py <パスワードを書いたファイル>

app.bin を key.json の秘密鍵（パスワードで開く）で復号し、
中身のHTMLに主な目印が残っているかを見て PASS / FAIL を出す。
パスワードはこのリポジトリには置かない。
"""
import base64, gzip, json, sys, unicodedata
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

def norm(p):
    p = unicodedata.normalize("NFKC", p).lower()
    for ch in " \t\n　-ー－‐―":
        p = p.replace(ch, "")
    return p

pw = open(sys.argv[1]).read()
ok = True
for app in ["sozoku", "shohi"]:
    kj = json.load(open(f"{app}/key.json")); b = base64.b64decode
    kek = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=b(kj["salt"]),
                     iterations=kj["iter"]).derive(norm(pw).encode())
    try:
        pkcs8 = AESGCM(kek).decrypt(b(kj["iv"]), b(kj["data"]), None)
    except Exception as e:
        print(f"{app}: NG 既存パスワードで開けません ({e})"); ok = False; continue
    priv = serialization.load_der_private_key(pkcs8, password=None)
    buf = open(f"{app}/app.bin", "rb").read()
    n = int.from_bytes(buf[4:6], "big")
    cek = priv.decrypt(buf[6:6+n], padding.OAEP(mgf=padding.MGF1(hashes.SHA256()),
                                                algorithm=hashes.SHA256(), label=None))
    html = gzip.decompress(AESGCM(cek).decrypt(buf[6+n:18+n], buf[18+n:], None)).decode("utf-8")
    need = ["isComposing", "compositionend", "::selection", ".searchrow{position:relative",
            'const REC={}', 'tts:"device"', "オフライン版"]
    miss = [x for x in need if x not in html]
    print(f"{app}: {'OK' if not miss else 'NG'} 既存パスワードで復号成功 {len(html):,}字  不足:{miss or 'なし'}")
    if miss: ok = False
print("RESULT:", "PASS" if ok else "FAIL")

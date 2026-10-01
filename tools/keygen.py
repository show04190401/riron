#!/usr/bin/env python3
"""パスワードを決め直して、鍵（tools/pubkey.pem と tools/key.json）を作り直す。

使い方:
    python3 tools/keygen.py

実行すると新しいパスワードを2回たずねられる。終わったら、必ず両方のアプリを
作り直すこと（鍵が変わるため、古い app.bin は新しいパスワードでは開けない）。

    python3 tools/build.py sozoku path/to/相続税アプリ.html
    python3 tools/build.py shohi  path/to/消費税アプリ.html

しくみ:
  - RSA-2048 の鍵ペアを作る。公開鍵は tools/pubkey.pem（build.py が本体の暗号化に使う）。
  - 秘密鍵（PKCS8 DER）を、パスワードから PBKDF2-SHA256 60万回で作った鍵で
    AES-256-GCM 暗号化し、tools/key.json に置く。
  - 端末側（index.html）は同じ手順で復号するので、パスワードの正規化もそろえてある。
"""
import base64, getpass, json, os, sys, unicodedata

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

TOOLS = os.path.dirname(os.path.abspath(__file__))
ITER = 600_000


def norm_pass(p):
    """端末側 index.html の normPass と同じ正規化。"""
    p = unicodedata.normalize("NFKC", p).lower()
    for ch in " \t\n　-ー－‐―":
        p = p.replace(ch, "")
    return p


def make(password):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pkcs8 = key.private_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    salt, iv = os.urandom(16), os.urandom(12)
    kek = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=ITER).derive(
        norm_pass(password).encode("utf-8")
    )
    data = AESGCM(kek).encrypt(iv, pkcs8, None)
    b64 = lambda b: base64.b64encode(b).decode()
    keyjson = {"v": 1, "kdf": "PBKDF2-SHA256", "iter": ITER,
               "salt": b64(salt), "iv": b64(iv), "data": b64(data)}
    with open(os.path.join(TOOLS, "key.json"), "w", encoding="utf-8") as f:
        json.dump(keyjson, f)
    with open(os.path.join(TOOLS, "pubkey.pem"), "wb") as f:
        f.write(key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ))
    print("tools/pubkey.pem と tools/key.json を作り直しました。")
    print("続けて build.py を両方のアプリで実行してください。")


if __name__ == "__main__":
    p1 = os.environ.get("RIRON_PASSWORD") or getpass.getpass("新しいパスワード: ")
    if not p1.strip():
        sys.exit("パスワードが空です。")
    if not os.environ.get("RIRON_PASSWORD"):
        if p1 != getpass.getpass("もう一度: "):
            sys.exit("一致しませんでした。")
    make(p1)

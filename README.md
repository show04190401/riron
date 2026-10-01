# 理論アプリ オフライン版

税理士試験の理論学習アプリ（相続税・消費税）を、iPhone・iPadのホーム画面に追加して通信なしで使うための置き場所です。

- `sozoku/` 相続税 理論、`shohi/` 消費税 理論
- アプリ本体（`app.bin`）は暗号化してあり、パスワードがないと開けません。
- 各アプリはサービスワーカー（`sw.js`）でファイルを端末に保存し、オフラインで開けるようにしています。

## 作り直し方

claude.ai 版のアプリのHTMLから作ります（パスワードは不要）。

```
pip install cryptography
python3 tools/build.py sozoku 相続税アプリ.html
python3 tools/build.py shohi  消費税アプリ.html
```

`app.bin` と `sw.js` が更新され、端末では次に通信できるときに新しい版が届きます。

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

## パスワードを変えるとき

パスワードを忘れた場合や変えたい場合は、鍵ごと作り直します。

```
python3 tools/keygen.py          # 新しいパスワードを2回入力する
python3 tools/build.py sozoku 相続税アプリ.html
python3 tools/build.py shohi  消費税アプリ.html
```

鍵が変わるため、`build.py` は必ず両方のアプリで実行してください。すでに端末に入れてある
アプリは、通信できるときに新しい版を受け取ったあと、もう一度パスワードを聞いてきます。

## 収支note（pnl/）

株の損益と資金繰りの記録アプリ。`pnl/` をiPhoneのホーム画面に追加して使います。データは端末内（Safari）に保存され、Claude上の「収支ノート」とは別です。

作り直し方（Claude上の収支ノートのHTMLから）:

```
python3 tools/build_pnl.py 収支ノート.html pnl/index.html
```

`pnl/sw.js` の `CACHE` の版（`v1` など）を上げると、端末に新しい版が届きます。

### データの保存とバックアップ（pnl/）

- 保存先：iPhoneのホーム画面アプリ内（ブラウザの localStorage、キー `pnl-notebook-v1`）。外部への通信はしません（フォントも端末標準）。
- 自動バックアップ：その日に最初に保存する前の状態を、端末内に直近7日分（キー `pnl-notebook-backups`）。
- 手動バックアップ：アプリ下部「データの書き出し・読み込み」→「ファイルに保存」（.json）。復元は「ファイルから復元」。
- 読み込み・復元の前の状態は自動で控え（キー `pnl-notebook-undo`）を取り、「読み込む前のデータに戻す」で戻せます。
- 読めない保存データがあった場合は、`pnl-notebook-v1-broken-<時刻>` に原本を残します。

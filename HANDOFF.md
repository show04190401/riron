# 理論アプリ（相続税・消費税）引き継ぎメモ

新しいセッションでこの続きをするときは、これを読めば再開できます。

## 1. いま何があるか

| もの | 置き場所 |
| --- | --- |
| アプリ本体（元のHTML。これが最新で、唯一の正本） | claude.ai の Artifact 2本（下記） |
| オフライン版（ホーム画面に追加して使う版） | GitHub `show04190401/riron` |
| 作り直しの道具 | 同リポジトリ `tools/build.py`, `tools/verify_build.py` |

- 相続税 理論：`https://claude.ai/artifact/VvfoLBSFSnjdFJZFkAKzBS`（版 167）
- 消費税 理論：`https://claude.ai/artifact/LoVqaD5331YC5y7fsZYjLX`（版 63）
- オフライン版の最新：相続税 `20261017-d16c3c20ec` / 消費税 `20261017-c0dce358b6`

リポジトリには**元のHTMLは入っていません**（入っているのは暗号化した `app.bin`）。
元のHTMLは必ず Artifact から取ってください。

## 2. 新しいセッションでの手順

1. Artifact を `read`（URL を渡す）して、HTMLを手元のファイルに落とす。
   例：`/home/claude/src2/sozoku/index.html`, `/home/claude/src2/shohi/index.html`
2. そのファイルを直す。
3. Artifact に `url` を付けて publish（同じURLに上書きされる。`url` を付けないと別物ができる）。
4. オフライン版を作り直す：
   ```
   git clone https://github.com/show04190401/riron
   cd riron
   python3 tools/build.py sozoku /path/to/sozoku/index.html
   python3 tools/build.py shohi  /path/to/shohi/index.html
   python3 tools/verify_build.py <パスワードを書いたファイル>   # 任意。PASS が出れば中身は元に戻る
   git add -A && git commit && git push
   ```
   - 作り直し（build）にパスワードは要りません。`verify_build.py` を走らせるときだけ要ります。
   - パスワードはリポジトリにもこのメモにも書いていません（端末で最初の1回だけ入れるもの）。

## 3. 作業のときの決めごと

- 2つのアプリ（相続税・消費税）は**同じ直しを両方に入れる**。
- 直したら publish の前に、headless Chromium（Playwright、`/opt/pw-browsers/chromium`）で
  位置や高さを実際に測って確かめる。見た目の話は目で見て確かめる。
- `build.py` は、アプリ側の目印が見つからないと止まる（`must_sub`）。
  アプリ側で該当箇所を書き換えたときは `build.py` も直す。
- 文章の表現は、ですます調・やさしい日本語。
- 教材（大原の理論テキスト等）の本文をアプリに貼り付けることはしない。

## 4. いまの画面の形（2026-10-17 時点）

- ホーム：まん中に「テキスト」「問題集」、下に「学習」、右上に「設定」。
- 上の帯：戻る / 🏠（最初の画面へ）／タイトル／🔍（検索。押したときだけ検索欄が出る）／設定。
  ホーム画面のタイトルは「2027年　○○税法　試験まであと○日」、それ以外は「○○税法」だけ。
- 問題集：記述・選択・正誤・復習・付箋。選択と正誤だけ、いちばん上に「ランダム」。
- 暗記（テキスト）：章を開くと目次（1-1, 1-2…）が出て、選んだ規定だけを出す。
- 問題カード：いちばん上の行の左に★、右に再生・付箋・メモ。問題番号はその下の行。

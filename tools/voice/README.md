# 録音の声（VOICEVOX）の作り方

オフライン版の「読み上げの声」で選べる声（2026-11-27〜）。暗記の本文と規定の名前を、あらかじめ作った音声で読む。

| 声のキー | 設定に出る名前 | VOICEVOX | vvm | スタイルID |
| --- | --- | --- | --- | --- |
| `no7` | No.7（女性） | No.7 アナウンス | 6 | 30 |
| `aoyama` | 青山龍星（男性） | 青山龍星 ノーマル | 15 | 13 |

- クレジット「VOICEVOX:No.7」「VOICEVOX:青山龍星」は、アプリの設定（音声 → 読み上げの声）に出している。個人の学習用（非営利）なので、どちらの声の規約でも使える。
- 区切り・読み・間は、アプリの `speechSegs`（端末の声と同じ区切り）をそのまま使う。区切りごとに音声を作り、区切りの後の間（「、」0.25秒・「。」0.6秒・見出しの後1秒など）を無音で入れて1つのファイルにつなぐ。区切りごとの開始秒（`st`）とハッシュ（`h`。アプリの `recH`）を目録に入れるので、途中から再生でき、文を直した問題は自動で端末の声になる。
- ファイルは AAC（m4a、24kHz・40kbps・モノラル）を暗号化したもの（先頭 `RIA1`、公開鍵で包んだ鍵＋AES-GCM。app.bin と同じ考え方）。端末ではアプリが秘密鍵（端末に保存済み）で復号して鳴らす。
- 端末では、設定の「この声を端末に保存」で全部のファイルを保存できる（`riron-<app>-voice` というキャッシュ。版が変わっても消えない。目録にない古いファイルはアプリが消す）。

## 作り直す手順

1. 作業用の環境（Python 3.12）
   ```
   uv venv --python 3.12 .venv && . .venv/bin/activate
   uv pip install "numpy<2" cryptography pyopenjtalk \
     https://github.com/VOICEVOX/voicevox_core/releases/download/0.16.2/voicevox_core-0.16.2-cp310-abi3-manylinux_2_34_x86_64.whl
   curl -LO https://github.com/VOICEVOX/onnxruntime-builder/releases/download/voicevox_onnxruntime-1.17.3/voicevox_onnxruntime-linux-x64-1.17.3.tgz
   curl -L -o vvms/6.vvm  https://github.com/VOICEVOX/voicevox_vvm/releases/download/0.16.2/6.vvm
   curl -L -o vvms/15.vvm https://github.com/VOICEVOX/voicevox_vvm/releases/download/0.16.2/15.vvm
   ```
   `gen.py` の先頭のパス（ORT・DIC・vvm の場所）を環境に合わせる。DIC は open_jtalk_dic_utf_8-1.11（pyopenjtalk が最初に使うときに取ってくる）。
2. いまのアプリの区切りを書き出す（オフライン版を復号した HTML か、claude.ai 版の HTML を使う）
   ```
   NODE_PATH=$(npm root -g) node segs.js hojin     # → hojin.segs.json
   ```
3. 音声を作る（作り終えた件は飛ばすので、止まっても続きから動く。法人税は1つの声で約2時間）
   ```
   python -I gen.py hojin no7 6 30
   python -I gen.py hojin aoyama 15 13
   ```
4. オフライン版の置き場所へ移して、作り直す
   ```
   python3 tools/voice/export.py hojin no7 <gen.py の出力>/hojin/no7 hojin.segs.json
   python3 tools/build.py hojin <アプリのHTML>
   ```
   `tools/voices/<app>.json`（目録）と `<app>/voice/<声>/` が更新される。build は目録があれば自動で声を入れる。

"""理論アプリの暗記を VOICEVOX で読み上げ、オフライン版用の音声ファイル（暗号化）と目録を作る。

使い方: python gen.py <app> <voice-key> <vvm番号> <スタイルID> [件数の上限]
  出力: /home/claude/work/out/<app>/<voice-key>/<name>.bin と rec.jsonl（1行1件の目録）
  途中で止めても、もう一度動かせば続きから作る（作り終えた件は飛ばす）。
"""
import hashlib, io, json, os, subprocess, sys, time, wave
import numpy as np
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from voicevox_core.blocking import Onnxruntime, OpenJtalk, Synthesizer, VoiceModelFile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from yomi import fix

TTS = "/home/claude/tts"
ORT = f"{TTS}/vv/voicevox_onnxruntime-linux-x64-1.17.3/lib/libvoicevox_onnxruntime.so.1.17.3"
DIC = f"{TTS}/.venv/lib/python3.12/site-packages/pyopenjtalk/open_jtalk_dic_utf_8-1.11"
PUB = serialization.load_pem_public_key(open("/home/claude/riron/tools/pubkey.pem", "rb").read())
SR = 24000

app, vkey, vvm, sid = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
limit = int(sys.argv[5]) if len(sys.argv) > 5 else None
items = json.load(open(f"/home/claude/work/{app}.segs.json"))
if limit: items = items[:limit]
out = f"/home/claude/work/out/{app}/{vkey}"
os.makedirs(out, exist_ok=True)
man = f"{out}/rec.jsonl"
done = {}
if os.path.exists(man):
    for line in open(man, encoding="utf-8"):
        r = json.loads(line); done[r["rk"]] = r

syn = Synthesizer(Onnxruntime.load_once(filename=ORT), OpenJtalk(DIC), cpu_num_threads=2)
with VoiceModelFile.open(f"{TTS}/vv/vvms/{vvm}.vvm") as m:
    syn.load_voice_model(m)


def say(text):
    q = syn.create_audio_query(text, sid)
    q.pre_phoneme_length = 0.05
    q.post_phoneme_length = 0.08
    wav = syn.synthesis(q, sid)
    with wave.open(io.BytesIO(wav)) as w:
        assert w.getframerate() == SR and w.getnchannels() == 1 and w.getsampwidth() == 2
        return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)


def encrypt(data):
    cek, iv = os.urandom(32), os.urandom(12)
    ct = AESGCM(cek).encrypt(iv, data, None)
    wrapped = PUB.encrypt(cek, padding.OAEP(mgf=padding.MGF1(hashes.SHA256()), algorithm=hashes.SHA256(), label=None))
    return b"RIA1" + len(wrapped).to_bytes(2, "big") + wrapped + iv + ct


t_start, secs, n_new = time.time(), 0.0, 0
for k, it in enumerate(items):
    say_t = [fix(app, s["t"]) for s in it["segs"]]  # 読み間違いを直した文（音声を作るときだけ使う）
    kk = [vkey, vvm, sid, it["rk"], it["segs"], it["tail"]]
    if any(t != s["t"] for t, s in zip(say_t, it["segs"])):
        kk.append(say_t)  # 直した問題だけ名前が変わり、作り直される
    key = hashlib.sha256(json.dumps(kk, ensure_ascii=False).encode()).hexdigest()[:12]
    name = f"{key}.bin"
    if it["rk"] in done and done[it["rk"]]["f"] == f"{vkey}/{name}" and os.path.exists(f"{out}/{name}"):
        continue
    parts, st, pos = [], [], 0
    for i, s in enumerate(it["segs"]):
        st.append(round(pos / SR, 3))
        a = say(say_t[i])
        gap = it["tail"] if i == len(it["segs"]) - 1 else s["g"]
        sil = np.zeros(int(SR * gap / 1000), dtype=np.int16)
        parts += [a, sil]; pos += len(a) + len(sil)
    pcm = np.concatenate(parts)
    tmp = f"/tmp/gen-{app}-{vkey}.m4a"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "s16le", "-ar", str(SR), "-ac", "1", "-i", "pipe:0",
                    "-c:a", "aac", "-b:a", "40k", "-movflags", "+faststart", tmp],
                   input=pcm.tobytes(), capture_output=True, check=True)
    enc = open(tmp, "rb").read()
    open(f"{out}/{name}", "wb").write(encrypt(enc))
    rec = {"rk": it["rk"], "f": f"{vkey}/{name}", "h": "".join(s["h"] for s in it["segs"]), "st": st, "dur": round(pos / SR, 1), "bytes": len(enc)}
    with open(man, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    done[it["rk"]] = rec
    secs += pos / SR; n_new += 1
    if n_new % 10 == 0 or k == len(items) - 1:
        el = time.time() - t_start
        print(f"{app}/{vkey}: {len(done)}/{len(items)}  audio {secs/60:.1f}min in {el/60:.1f}min (x{secs/max(el,1):.2f})", flush=True)
print(f"DONE {app}/{vkey}: {len(done)}/{len(items)}", flush=True)

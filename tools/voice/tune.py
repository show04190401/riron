"""声の調子の手直し（VOICEVOX の AudioQuery を、音声を作る前に直す）。

- merge_tou：読みの手直しで「等」を「とう」にした所は、独立した語（頭高）になり「…社団 トウに」と強く聞こえる。
  「とう＋助詞」だけのアクセント句を前の句につなげて、ふつうの「…社団等に」の抑揚にする。
- calm：抑揚を少し弱め（intonation_scale）、文の後ろへ行くほど少しずつ声を下げる（自然な下がり方）。
  No.1（No.7 アナウンス）の長い文で、後半が強く威圧的に聞こえるのを抑える（2026-11-28 ユーザーの指摘）。
"""
import re
from voicevox_core import AccentPhrase

TOU = re.compile(r"トオ(ニ|ノ|ワ|ガ|オ|ヲ|デ|ト|モ|ヘ|カラ|マデ|ヨリ|ニワ|ノウチ|デワ)?")


def merge_tou(aps):
    out = []
    for ap in aps:
        t = "".join(m.text for m in ap.moras)
        if out and out[-1].pause_mora is None and TOU.fullmatch(t):
            p = out[-1]
            out[-1] = AccentPhrase(moras=p.moras + ap.moras, accent=p.accent, pause_mora=ap.pause_mora, is_interrogative=ap.is_interrogative)
            continue
        out.append(ap)
    return out


def apply(syn, q, sid, opt):
    """opt: {"merge_tou": bool, "intonation": float, "decline": float}"""
    if not opt:
        return q
    if opt.get("merge_tou"):
        q.accent_phrases = syn.replace_mora_pitch(merge_tou(q.accent_phrases), sid)
    if "intonation" in opt:
        q.intonation_scale = opt["intonation"]
    d = opt.get("decline", 0)
    if d:
        ms = [m for ap in q.accent_phrases for m in ap.moras if m.pitch > 0]
        n = max(1, len(ms) - 1)
        for k, m in enumerate(ms):
            m.pitch -= d * k / n
    return q


# 声ごとの手直し（gen.py が使う。ここを変えると、その声の音声は作り直しになる）
VOICE_TUNE = {
    # No.1：「等」の抑揚を直し、抑揚を少し弱めて、文の後ろへ行くほど少し下げる（調整案B。2026-11-28）
    "no7": {"merge_tou": True, "intonation": 0.85, "decline": 0.06},
}

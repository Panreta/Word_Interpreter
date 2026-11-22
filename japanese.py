"""Japanese pronunciation analysis from the OpenJTalk dictionary."""

import re

import pyopenjtalk

# --------------------------------------------------------------------------
# Reading, morae, pitch accent, romaji (OpenJTalk dictionary)
# --------------------------------------------------------------------------

SMALL_KANA = set("ャュョァィゥェォヮ")
DEVOICE_MARK = "’"

ROMAJI = {
    "ア": "a", "イ": "i", "ウ": "u", "エ": "e", "オ": "o",
    "カ": "ka", "キ": "ki", "ク": "ku", "ケ": "ke", "コ": "ko",
    "ガ": "ga", "ギ": "gi", "グ": "gu", "ゲ": "ge", "ゴ": "go",
    "サ": "sa", "シ": "shi", "ス": "su", "セ": "se", "ソ": "so",
    "ザ": "za", "ジ": "ji", "ズ": "zu", "ゼ": "ze", "ゾ": "zo",
    "タ": "ta", "チ": "chi", "ツ": "tsu", "テ": "te", "ト": "to",
    "ダ": "da", "ヂ": "ji", "ヅ": "zu", "デ": "de", "ド": "do",
    "ナ": "na", "ニ": "ni", "ヌ": "nu", "ネ": "ne", "ノ": "no",
    "ハ": "ha", "ヒ": "hi", "フ": "fu", "ヘ": "he", "ホ": "ho",
    "バ": "ba", "ビ": "bi", "ブ": "bu", "ベ": "be", "ボ": "bo",
    "パ": "pa", "ピ": "pi", "プ": "pu", "ペ": "pe", "ポ": "po",
    "マ": "ma", "ミ": "mi", "ム": "mu", "メ": "me", "モ": "mo",
    "ヤ": "ya", "ユ": "yu", "ヨ": "yo",
    "ラ": "ra", "リ": "ri", "ル": "ru", "レ": "re", "ロ": "ro",
    "ワ": "wa", "ヲ": "o", "ヴ": "vu",
    "ァ": "a", "ィ": "i", "ゥ": "u", "ェ": "e", "ォ": "o",
    "ャ": "ya", "ュ": "yu", "ョ": "yo", "ヮ": "wa",
    "シャ": "sha", "シュ": "shu", "ショ": "sho", "シェ": "she",
    "ジャ": "ja", "ジュ": "ju", "ジョ": "jo", "ジェ": "je",
    "チャ": "cha", "チュ": "chu", "チョ": "cho", "チェ": "che",
    "ヂャ": "ja", "ヂュ": "ju", "ヂョ": "jo",
    "ティ": "ti", "ディ": "di", "トゥ": "tu", "ドゥ": "du", "デュ": "dyu",
    "ファ": "fa", "フィ": "fi", "フェ": "fe", "フォ": "fo", "フュ": "fyu",
    "ウィ": "wi", "ウェ": "we", "ウォ": "wo",
    "ヴァ": "va", "ヴィ": "vi", "ヴェ": "ve", "ヴォ": "vo",
    "ツァ": "tsa", "ツィ": "tsi", "ツェ": "tse", "ツォ": "tso",
}
MACRON = {"a": "ā", "i": "ī", "u": "ū", "e": "ē", "o": "ō"}


def to_hiragana(text):
    return "".join(chr(ord(c) - 0x60) if "ァ" <= c <= "ヶ" else c for c in text)


def split_morae(kana):
    """Split katakana into morae; returns [(mora, devoiced), ...]."""
    morae = []
    for ch in kana:
        if ch == DEVOICE_MARK:
            if morae:
                morae[-1] = (morae[-1][0], True)
        elif ch in SMALL_KANA and morae and morae[-1][0] not in "ッン":
            morae[-1] = (morae[-1][0] + ch, morae[-1][1])
        else:
            morae.append((ch, False))
    return morae


def mora_romaji(mora):
    if mora in ROMAJI:
        return ROMAJI[mora]
    # e.g. キャ -> ki + ya -> kya
    base, small = ROMAJI.get(mora[0], mora[0]), ROMAJI.get(mora[1:], mora[1:])
    if small.startswith("y"):
        return base[:-1] + small
    return base[:-1] + small


def morae_to_romaji(morae):
    out = ""
    for i, mora in enumerate(morae):
        nxt = morae[i + 1] if i + 1 < len(morae) else None
        if mora == "ー":
            if out and out[-1] in MACRON:
                out = out[:-1] + MACRON[out[-1]]
        elif mora == "ッ":
            if nxt and nxt not in "ーッン":
                r = mora_romaji(nxt)
                out += "t" if r.startswith("ch") else r[0]
        elif mora == "ン":
            out += "n'" if nxt and mora_romaji(nxt)[0] in "aiueoy" else "n"
        else:
            out += mora_romaji(mora)
    return out


def accent_phrases_from_labels(word):
    """Return [(mora_count, accent_type), ...] per accent phrase."""
    phrases = []
    prev_a2 = None
    for label in pyopenjtalk.extract_fullcontext(word):
        a = re.search(r"/A:([\-\d]+)\+(\d+)\+", label)
        f = re.search(r"/F:(\d+)_(\d+)", label)
        if not a or not f:  # silence / pause
            prev_a2 = None
            continue
        a2 = int(a.group(2))
        if prev_a2 is None or a2 < prev_a2:
            phrases.append((int(f.group(1)), int(f.group(2))))
        prev_a2 = a2
    return phrases


def pitch_pattern(n_morae, accent):
    if accent == 0:
        pattern = "L" + "H" * (n_morae - 1)
        name = "heiban (flat — no drop; a following particle stays high)"
    elif accent == 1:
        pattern = "H" + "L" * (n_morae - 1)
        name = "atamadaka (high first mora, then drops)"
    else:
        pattern = "L" + "H" * (accent - 1) + "L" * (n_morae - accent)
        if accent == n_morae:
            name = "odaka (drops only on a following particle)"
        else:
            name = f"nakadaka (drops after mora {accent})"
    return pattern, name


def analyze(word):
    features = pyopenjtalk.run_frontend(word)
    reading = to_hiragana("".join(f["read"] for f in features))
    pron = "".join(f["pron"] for f in features)
    morae = split_morae(pron)
    mora_text = [m for m, _ in morae]

    # Labels can't distinguish heiban from odaka (both read as accent == length),
    # so check the head word's dictionary accent: 0 means heiban.
    head_accents = [f["acc"] for f in features if f["chain_flag"] != 1]
    label_phrases = accent_phrases_from_labels(word)
    phrases = []
    for k, (n, acc) in enumerate(label_phrases):
        if acc == n and len(head_accents) == len(label_phrases) and head_accents[k] == 0:
            acc = 0
        phrases.append((n, acc) + pitch_pattern(n, acc))
    if sum(p[0] for p in phrases) != len(morae):
        phrases = []  # label/mora mismatch (e.g. symbols); skip pitch info

    # Romaji per accent phrase so multi-word input stays readable.
    romaji_parts, i = [], 0
    for n, *_ in phrases or [(len(mora_text),)]:
        romaji_parts.append(morae_to_romaji(mora_text[i:i + n]))
        i += n

    return {
        "word": word,
        "reading": reading,
        "pronounced": to_hiragana(pron.replace(DEVOICE_MARK, "")),
        "morae": [to_hiragana(m) for m in mora_text],
        "devoiced": [to_hiragana(m) for m, d in morae if d],
        "romaji": " ".join(romaji_parts),
        "phrases": phrases,
    }

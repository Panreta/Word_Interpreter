"""Target languages and their pronunciation analysis.

Every analysis comes from a dictionary or phonemizer, never from the LLM:
  ja  - OpenJTalk (reading, morae, pitch accent)
  zh  - pypinyin (pinyin and tones, including tone changes)
  yue - ToJyutping (Jyutping and tones)
  en  - Kokoro's English phonemizer (IPA)
  es  - Kokoro's Spanish phonemizer via espeak-ng (IPA)
"""

import re

import japanese

# code -> display name, how to describe it to the LLM, voices (first is default)
TARGETS = {
    "ja": {
        "name": "日本語 Japanese",
        "llm": "Japanese",
        "voices": ["jf_alpha", "jf_gongitsune", "jf_nezumi", "jf_tebukuro", "jm_kumo"],
    },
    "zh": {
        "name": "普通话 Mandarin",
        "llm": "Mandarin Chinese",
        "voices": ["zf_xiaoxiao", "zf_xiaoyi", "zf_xiaobei", "zf_xiaoni",
                   "zm_yunxi", "zm_yunjian", "zm_yunyang", "zm_yunxia"],
    },
    "yue": {
        "name": "粵語 Cantonese",
        "llm": "Cantonese",
        # Kokoro has no Cantonese voice, so these are edge-tts (Microsoft) voices.
        "voices": ["zh-HK-HiuGaaiNeural", "zh-HK-HiuMaanNeural", "zh-HK-WanLungNeural"],
    },
    "en": {
        "name": "English",
        "llm": "English",
        "voices": ["af_heart", "af_bella", "af_nicole", "am_michael", "am_fenrir",
                   "bf_emma", "bm_george"],
    },
    "es": {
        "name": "Español Spanish",
        "llm": "Spanish",
        "voices": ["ef_dora", "em_alex", "em_santa"],
    },
}

HAN = r"[㐀-䶿一-鿿豈-﫿]"
MANDARIN_TONES = {1: "1st tone (high level)", 2: "2nd tone (rising)",
                  3: "3rd tone (low dipping)", 4: "4th tone (falling)", 5: "neutral tone (light)"}
CANTONESE_TONES = {1: "tone 1 (high level)", 2: "tone 2 (high rising)", 3: "tone 3 (mid level)",
                   4: "tone 4 (low falling)", 5: "tone 5 (low rising)", 6: "tone 6 (low level)"}


def analyze(word, target):
    return {"ja": analyze_japanese, "zh": analyze_mandarin, "yue": analyze_cantonese,
            "en": analyze_ipa, "es": analyze_ipa}[target](word, target)


def analyze_japanese(word, target):
    info = japanese.analyze(word)
    info["phrases"] = [{"morae": n, "accent": acc, "pattern": pattern, "name": name}
                       for n, acc, pattern, name in info["phrases"]]
    info.update(target=target, romanization=info["romaji"])
    return info


def analyze_mandarin(word, target):
    from pypinyin import Style, lazy_pinyin

    chars = [c for c in word if re.match(HAN, c)]
    text = "".join(chars)
    # Written pinyin uses citation tones; spoken applies tone changes (你好 nǐ hǎo -> ní hǎo).
    written = lazy_pinyin(text, style=Style.TONE)
    spoken = lazy_pinyin(text, style=Style.TONE, tone_sandhi=True)
    numbers = lazy_pinyin(text, style=Style.TONE3, neutral_tone_with_five=True, tone_sandhi=True)
    units = [{"text": c, "roman": s, "tone": int(n[-1]) if n[-1].isdigit() else 5}
             for c, s, n in zip(chars, spoken, numbers)]
    return {
        "target": target, "word": word, "units": units,
        "romanization": " ".join(written),
        "spoken": " ".join(spoken) if spoken != written else None,
    }


def analyze_cantonese(word, target):
    import ToJyutping

    units = [{"text": c, "roman": j, "tone": int(j[-1])}
             for c, j in ToJyutping.get_jyutping_list(word) if j]
    return {"target": target, "word": word, "units": units,
            "romanization": " ".join(u["roman"] for u in units)}


def analyze_ipa(word, target):
    import speech
    return {"target": target, "word": word, "units": [],
            "romanization": f"/{speech.phonemes(word, target)}/"}


def split_words(word, target):
    """The word's parts, in order, for a word-by-word breakdown (from a tokenizer, not the LLM)."""
    if target == "ja":
        parts = japanese.split_words(word)
    elif target in ("zh", "yue"):
        parts = split_chinese(word)
    else:
        parts = [w.strip(".,!?¡¿;:\"'()") for w in word.split()]
    return [p for p in parts if p.strip()]


def split_chinese(word):
    import logging

    import jieba
    jieba.setLogLevel(logging.ERROR)
    parts = [w for w in jieba.lcut(word) if re.search(HAN, w)]
    if len(parts) == 1 and len(word) > 2:
        # A single compound (火车站): split off its longest known leading word (火车 + 站).
        for n in range(len(word) - 1, 1, -1):
            if jieba.dt.FREQ.get(word[:n]):
                return [word[:n], word[n:]]
    return parts


def llm_facts(info):
    """Verified pronunciation data handed to the LLM so its tips stay grounded."""
    target = info["target"]
    facts = {"language": TARGETS[target]["llm"], "word": info["word"]}
    if target == "ja":
        facts.update({
            "reading": info["reading"],
            "actual pronunciation": info["pronounced"],
            "morae": info["morae"],
            "romaji": info["romaji"],
            "devoiced morae": info["devoiced"] or "none",
            "long vowels (ー)": info["morae"].count("ー") or "none",
            "double consonants (っ)": info["morae"].count("っ") or "none",
            "moraic n (ん)": info["morae"].count("ん") or "none",
            "pitch": [f"{p['pattern']} - {p['name']}" for p in info["phrases"]],
        })
    elif target in ("zh", "yue"):
        names = MANDARIN_TONES if target == "zh" else CANTONESE_TONES
        facts["romanization"] = info["romanization"]
        if info.get("spoken"):
            facts["spoken with tone changes"] = info["spoken"]
        facts["syllables"] = [f"{u['text']} {u['roman']}: {names[u['tone']]}" for u in info["units"]]
    else:
        facts["IPA"] = info["romanization"]
    return facts


def is_valid_word(text, target):
    """Check the LLM's translation is actually written in the target language's script."""
    has_latin = re.search(r"[A-Za-z]", text)
    has_kana = re.search(r"[぀-ヿ]", text)
    has_han = re.search(HAN, text)
    if target == "ja":
        return bool(has_kana or has_han) and not has_latin
    if target in ("zh", "yue"):
        return bool(has_han) and not (has_latin or has_kana)
    return bool(has_latin) and not (has_kana or has_han)

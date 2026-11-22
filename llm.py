"""Free local LLM (via Ollama): translation into the target language, and explanations."""

import json
import os
import re

import requests

from languages import TARGETS, is_valid_word, llm_facts

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
DEFAULT_MODEL = os.environ.get("WORD_INTERPRETER_MODEL", "qwen2.5:7b")

SOURCE_LANGUAGES = {"ja": "Japanese", "zh": "Chinese", "en": "English", "es": "Spanish"}

# How to tell the LLM to write the meaning and tips, per output language.
EXPLAIN_LANGUAGES = {
    "en": "English",
    "zh": "Mandarin Chinese, in Simplified characters",
    "yue": "Cantonese, written as colloquial Hong Kong Cantonese in Traditional characters "
           "(use 係、嘅、呢個、唔, not Mandarin 是、的、这个、不)",
    "es": "Spanish",
    "ja": "simple Japanese suitable for a learner",
}


class LLMError(Exception):
    pass


LLM_ERRORS = (requests.ConnectionError, requests.HTTPError, LLMError)


def error_message(e, model=DEFAULT_MODEL):
    if isinstance(e, LLMError):
        return str(e)
    if isinstance(e, requests.ConnectionError):
        return f"cannot reach Ollama at {OLLAMA_URL} — run `ollama serve`"
    return f"{e.response.text.strip()} — try `ollama pull {model}`"


def ask_ollama(system, user, schema, model, temperature=0.2):
    # Small models occasionally loop and emit truncated JSON; retry once, warmer.
    for attempt_temperature in (temperature, max(temperature, 0.7)):
        resp = requests.post(
            f"{OLLAMA_URL}/api/chat",
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "format": schema,
                "stream": False,
                "options": {"temperature": attempt_temperature, "repeat_penalty": 1.15,
                            "num_predict": 400},
            },
            timeout=180,
        )
        resp.raise_for_status()
        try:
            return json.loads(resp.json()["message"]["content"])
        except json.JSONDecodeError:
            continue
    raise LLMError("the model returned an invalid answer; please try again")


# --------------------------------------------------------------------------
# Translation
# --------------------------------------------------------------------------

def detect_script(text):
    """Return 'ja' (has kana), 'han' (CJK ideographs only), or 'latin'."""
    if re.search(r"[぀-ヿ]", text):
        return "ja"
    if re.search(r"[一-鿿]", text):
        return "han"
    return "latin"


TRANSLATION_SCHEMA = {
    "type": "object",
    "properties": {
        "source_language": {"type": "string", "enum": ["ja", "zh", "en", "es", "other"]},
        "translation": {"type": "string"},
        "alternatives": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["source_language", "translation", "alternatives"],
}

TARGET_NOTES = {
    "ja": "written the way Japanese people normally write it (kanji + kana as usual), using "
          "only Japanese script — never Chinese simplified characters that Japanese doesn't "
          "use (爱 → 愛, 吃饭 → ご飯を食べる) and never English letters",
    "zh": "in Simplified Chinese characters, using standard Mandarin wording",
    "yue": "in Traditional Chinese characters, using the word a Hong Kong Cantonese speaker "
           "would actually say (thank you → 多謝, eat → 食飯, what → 乜嘢)",
    "en": "in English",
    "es": "in Spanish",
}

TRANSLATION_PROMPT = """You translate words for a language learner.
The input is a word or short phrase in {source}. Translate it into {target}.
Respond ONLY with JSON:
- source_language: the input's language: "ja", "zh", "en", "es" or "other"
- translation: the single most natural, common {target} equivalent, {note}.
  If the input is already {target} with this meaning, return it unchanged.
- alternatives: up to 3 other common {target} words with a similar meaning (may be empty)"""


def translate(text, target, model, source="auto"):
    """Turn input in any language into a word in the target language.

    Returns {"source_language", "translation", "alternatives"}.
    """
    script = detect_script(text)
    if source == target or (source == "auto" and target == "ja" and script == "ja"):
        return {"source_language": target, "translation": text, "alternatives": []}

    if source != "auto":
        described = SOURCE_LANGUAGES[source]
    else:
        described = {"ja": "Japanese", "han": "Chinese or Japanese"}.get(script, "any language")
    system = TRANSLATION_PROMPT.format(source=described, target=TARGETS[target]["llm"],
                                       note=TARGET_NOTES[target])
    for temperature in (0, 0.6):  # retry once if the answer isn't in the target's script
        result = ask_ollama(system, text, TRANSLATION_SCHEMA, model, temperature)
        candidates = [c.strip() for c in [result["translation"], *result["alternatives"]]]
        valid = list(dict.fromkeys(c for c in candidates if c and is_valid_word(c, target)))
        if valid:
            result["translation"], result["alternatives"] = valid[0], valid[1:4]
            return result
    raise LLMError(f"couldn't translate “{text}” into {TARGETS[target]['llm']}; please try again")


# --------------------------------------------------------------------------
# Explanation
# --------------------------------------------------------------------------

EXPLANATION_SCHEMA = {
    "type": "object",
    "properties": {
        "meaning": {"type": "string"},
        "pronunciation_tips": {"type": "string"},
    },
    "required": ["meaning", "pronunciation_tips"],
}

TIP_FOCUS = {
    "ja": "long vowels, っ pauses, ん, devoiced vowels, the Japanese r, where the pitch rises/falls",
    "zh": "each syllable's tone, tone changes, aspirated vs unaspirated and retroflex consonants",
    "yue": "each syllable's tone (Cantonese has 6), final -p/-t/-k stops, the ng- initial",
    "en": "which syllable is stressed, vowel sounds, consonant clusters, th/r/l sounds",
    "es": "which syllable is stressed, pure vowels, tapped vs trilled r, soft b/d/g",
}

EXPLANATION_PROMPT = """You are a {target} pronunciation tutor.
You are given a {target} word together with VERIFIED pronunciation data from a
dictionary. Trust that data completely; do not contradict it, and only mention
features the data shows are present.
Write everything in {language} — both fields, including the meaning. Do not
explain the word in another language.
Respond ONLY with JSON:
- meaning: short meaning of the word, written in {language}
- pronunciation_tips: 2-3 short sentences, written in {language}, of practical
  advice for a learner, based on the given data ({focus})."""


def explain(info, model, lang="en"):
    target = info["target"]
    system = EXPLANATION_PROMPT.format(target=TARGETS[target]["llm"], focus=TIP_FOCUS[target],
                                       language=EXPLAIN_LANGUAGES[lang])
    facts = json.dumps(llm_facts(info), ensure_ascii=False)
    result = ask_ollama(system, facts, EXPLANATION_SCHEMA, model)
    # Small models sometimes drift into English; retry once, more firmly, for CJK output.
    if lang in ("ja", "zh", "yue") and mostly_latin(result["meaning"]):
        system += (f"\nIMPORTANT: the meaning must be written in {EXPLAIN_LANGUAGES[lang]}, "
                   "not in English. Explain it as a native-language dictionary would.")
        result = ask_ollama(system, facts, EXPLANATION_SCHEMA, model, temperature=0.7)
    return result


def mostly_latin(text):
    latin = len(re.findall(r"[A-Za-z]", text))
    cjk = len(re.findall(r"[\u3040-\u30ff\u4e00-\u9fff]", text))
    return latin > cjk

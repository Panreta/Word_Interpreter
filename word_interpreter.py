"""Word Interpreter: see and hear how to say a word in another language.

Type a word in any language and pick an output language (Japanese, Mandarin,
Cantonese, English or Spanish). Everything comes back in that language: the
word is translated by a free local LLM (via Ollama) if needed, then you get:
  * its pronunciation from a dictionary/phonemizer: Japanese reading, morae and
    pitch accent; Mandarin pinyin and tones; Cantonese Jyutping and tones;
    English/Spanish IPA,
  * its meaning and pronunciation tips, written in the output language (LLM),
  * the word spoken aloud (Kokoro TTS; edge-tts for Cantonese).

Usage:
    python word_interpreter.py 東京                     # Japanese (default target)
    python word_interpreter.py apple --to es           # -> manzana
    python word_interpreter.py "thank you" --to yue
    python word_interpreter.py                          # interactive mode
"""

import argparse
import os
import platform
import subprocess
import warnings

warnings.filterwarnings("ignore")

import speech
from languages import CANTONESE_TONES, MANDARIN_TONES, TARGETS, analyze
from llm import (DEFAULT_MODEL, LLM_ERRORS, SOURCE_LANGUAGES, error_message, explain,
                 translate)

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")


def play(path):
    system = platform.system()
    if system == "Darwin":
        subprocess.run(["afplay", path], check=False)
    elif system == "Linux":
        subprocess.run(["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", path], check=False)
    elif system == "Windows":
        os.startfile(path)


def format_pitch(info):
    lines = []
    i = 0
    for phrase in info["phrases"]:
        morae = info["morae"][i:i + phrase["morae"]]
        i += phrase["morae"]
        # Kana are double-width in a terminal, so pad by display width.
        width = max(len(m) for m in morae) * 2 + 1
        lines.append("".join(m + " " * (width - 2 * len(m)) for m in morae).rstrip())
        lines.append("".join(p.ljust(width) for p in phrase["pattern"]).rstrip()
                     + f"   {phrase['name']}")
    return lines


def print_pronunciation(info):
    target = info["target"]
    print(f"\n  {info['word']}")
    if target == "ja":
        print(f"  Reading     : {info['reading']}")
        if info["pronounced"] != info["reading"]:
            print(f"  Sounds like : {info['pronounced']}")
        print(f"  Romaji      : {info['romaji']}")
        print(f"  Morae       : {' · '.join(info['morae'])}  ({len(info['morae'])} beats)")
        if info["devoiced"]:
            print(f"  Devoiced    : {', '.join(info['devoiced'])} (vowel is whispered/nearly silent)")
        if info["phrases"]:
            print("  Pitch accent:")
            for line in format_pitch(info):
                print(f"      {line}")
    elif target in ("zh", "yue"):
        label, names = ("Pinyin", MANDARIN_TONES) if target == "zh" else ("Jyutping", CANTONESE_TONES)
        print(f"  {label:<12}: {info['romanization']}")
        if info.get("spoken"):
            print(f"  Sounds like : {info['spoken']}  (tone change)")
        for u in info["units"]:
            print(f"      {u['text']}  {u['roman']:<8} {names[u['tone']]}")
    else:
        print(f"  IPA         : {info['romanization']}")


def interpret(text, args):
    word = text
    if not args.no_llm:
        try:
            result = translate(text, args.to, args.model, args.source)
        except LLM_ERRORS as e:
            print(f"  (Translation skipped: {error_message(e, args.model)})")
        else:
            word = result["translation"]
            if word != text:
                lang = SOURCE_LANGUAGES.get(result["source_language"], "")
                print(f"\n  {text}{f' ({lang})' if lang else ''} → {word}")
                if result["alternatives"]:
                    print(f"  Also        : {', '.join(result['alternatives'])}")

    info = analyze(word, args.to)
    print_pronunciation(info)

    if not args.no_llm:
        try:
            extra = explain(info, args.model, args.to)
            print(f"  Meaning     : {extra['meaning']}")
            print(f"  Tips        : {extra['pronunciation_tips']}")
        except LLM_ERRORS as e:
            print(f"  (LLM skipped: {error_message(e, args.model)})")

    if args.no_audio:
        return
    audio = speech.synthesize(word, args.to, args.voice, args.slow)
    if audio is None:
        print("  (No audio produced)")
        return
    data, _, ext = audio
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    path = os.path.join(OUTPUT_DIR, f"{word}.{ext}")
    with open(path, "wb") as f:
        f.write(data)
    print(f"  Audio       : {path}")
    play(path)


def main():
    parser = argparse.ArgumentParser(description="See and hear how to say a word in another language")
    parser.add_argument("word", nargs="?", help="word in any language (omit for interactive mode)")
    parser.add_argument("--to", default="ja", choices=list(TARGETS),
                        help="output language (default: ja)")
    parser.add_argument("--from", dest="source", default="auto",
                        choices=["auto", *SOURCE_LANGUAGES], help="input language")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Ollama model name")
    parser.add_argument("--voice", help="voice (default: first voice for the target language)")
    parser.add_argument("--slow", action="store_true", help="speak more slowly")
    parser.add_argument("--no-audio", action="store_true", help="skip speech synthesis")
    parser.add_argument("--no-llm", action="store_true",
                        help="skip translation and the LLM explanation")
    args = parser.parse_args()

    voices = TARGETS[args.to]["voices"]
    if args.voice is None:
        args.voice = voices[0]
    elif args.voice not in voices:
        parser.error(f"voice for --to {args.to} must be one of: {', '.join(voices)}")

    if args.word:
        interpret(args.word.strip(), args)
        return

    print(f"Enter a word to say in {TARGETS[args.to]['name']} (empty line or Ctrl+D to quit).")
    while True:
        try:
            word = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not word:
            break
        interpret(word, args)


if __name__ == "__main__":
    main()

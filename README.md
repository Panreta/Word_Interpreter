# Word Interpreter

Type a word in any language, choose an **output language** — 日本語 Japanese, 普通话 Mandarin, 粵語 Cantonese, English or Español — and everything comes back in that language: the translated word, how to pronounce it, a native voice saying it, its meaning and tips, and the page itself.

| Output | Pronunciation shown (from a dictionary, not the LLM) | Voice |
|---|---|---|
| Japanese | reading, romaji, morae, pitch-accent diagram, devoiced vowels (OpenJTalk) | Kokoro |
| Mandarin | pinyin, tones with contour diagrams, tone changes like 你好 → ní hǎo (pypinyin) | Kokoro |
| Cantonese | Jyutping, tones with contour diagrams (ToJyutping) | edge-tts* |
| English | IPA (Kokoro's phonemizer) | Kokoro |
| Spanish | IPA (espeak-ng) | Kokoro |

Translation, meanings and tips come from a free local LLM through [Ollama](https://ollama.com), grounded in the dictionary data.

\* Kokoro has no Cantonese voice, so Cantonese audio uses [edge-tts](https://github.com/rany2/edge-tts) (free, but sends the word to Microsoft's online TTS service).

## Setup

Requires Python 3.10–3.12 (Kokoro doesn't support 3.13+ yet).

```bash
brew install espeak-ng                  # Spanish (and English fallback) phonemes
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -r requirements.txt
.venv/bin/python -m unidic download     # Japanese dictionary (~500 MB, one time)

ollama serve &                          # if Ollama isn't already running
ollama pull qwen2.5:7b                  # free LLM, ~4.7 GB
```

## Usage

### Web

```bash
.venv/bin/python web.py                # then open http://localhost:8765
```

### Command line

```bash
.venv/bin/python word_interpreter.py 東京                  # Japanese (default output)
.venv/bin/python word_interpreter.py apple --to es        # manzana
.venv/bin/python word_interpreter.py "thank you" --to yue # 多謝
.venv/bin/python word_interpreter.py                       # interactive mode
```

Options: `--to` (`ja`, `zh`, `yue`, `en`, `es`), `--from` (`auto`, `ja`, `zh`, `en`, `es`), `--voice`, `--slow`, `--model` (any Ollama model, or set `WORD_INTERPRETER_MODEL`), `--no-audio`, `--no-llm`.

## Code

- `languages.py` — output languages, voices, per-language pronunciation analysis
- `japanese.py` — Japanese reading, morae, pitch accent, romaji
- `speech.py` — Kokoro / edge-tts audio
- `llm.py` — translation and explanations via Ollama
- `word_interpreter.py` — CLI; `web.py` + `static/index.html` — web app

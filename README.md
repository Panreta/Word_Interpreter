# Word Interpreter

Type a Japanese word and learn how to pronounce it:

- **Reading, morae, romaji, pitch accent, devoiced vowels**: from the OpenJTalk dictionary (bundled with Kokoro's Japanese support), so they're reliable.
- **Meaning and pronunciation tips**: from a free local LLM through [Ollama](https://ollama.com), grounded in the dictionary data.
- **Audio**: spoken aloud with [Kokoro](https://github.com/hexgrad/kokoro) TTS and saved to `output/<word>.wav`.

## Setup

Requires Python 3.10–3.12 (Kokoro doesn't support 3.13+ yet).

```bash
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

Shows the reading, a pitch-accent diagram, meaning and tips, with Play / Slow buttons.

### Command line

```bash
.venv/bin/python word_interpreter.py 東京             # one word
.venv/bin/python word_interpreter.py                  # interactive mode
.venv/bin/python word_interpreter.py 勉強 --slow --voice jm_kumo
```

Options: `--model` (any Ollama model, or set `WORD_INTERPRETER_MODEL`), `--voice` (`jf_alpha`, `jf_gongitsune`, `jf_nezumi`, `jf_tebukuro`, `jm_kumo`), `--slow`, `--no-audio`, `--no-llm`.

Example:

```
  東京
  Reading     : とうきょう
  Sounds like : とーきょー
  Romaji      : tōkyō
  Morae       : と · ー · きょ · ー  (4 beats)
  Pitch accent:
      と   ー   きょ ー
      L    H    H    H   heiban (flat — no drop; a following particle stays high)
  Meaning     : Tokyo
  Tips        : ...
  Audio       : output/東京.wav
```

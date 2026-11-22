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

## Start the website

```bash
./start.sh
```

That's it. The script starts Ollama (if it isn't running), starts the web server, and opens **http://localhost:8765** in your browser. Press **Ctrl+C** in the terminal to stop — everything the script started is shut down, so nothing keeps running in the background.

The first start after setup takes ~10–20 seconds while models load; the first word you look up in each language takes a few seconds more.

### Use it from your phone or another computer (optional)

```bash
brew install cloudflared     # one time
./start.sh --public
```

This also prints a temporary public link like `https://random-words.trycloudflare.com` (a free [Cloudflare Quick Tunnel](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/do-more-with-tunnels/trycloudflare/) — no account, no cost). Notes:

- The link only works while `./start.sh --public` is running and your computer is awake.
- You get a new link every time you start it.
- Anyone with the link can use the site (running on your computer), so only share it with people you trust. Inputs are limited to 200 characters (`MAX_TEXT_LENGTH`) and 20 requests per minute per visitor (`RATE_LIMIT_PER_MINUTE`).

### If something goes wrong

| Message | Fix |
|---|---|
| `Python environment not found` | Do the one-time [Setup](#setup) below. |
| `Something is already running on port 8765` | It's probably already open — check your browser. Or use another port: `PORT=8766 ./start.sh` |
| `--public needs cloudflared` | `brew install cloudflared` |
| `Ollama not found` | Install it from [ollama.com](https://ollama.com). |
| Meaning/tips say "LLM unavailable" | Ollama stopped — restart `./start.sh`. |

## Setup

One time only. Requires macOS or Linux, [Ollama](https://ollama.com), and Python 3.10–3.12 (Kokoro doesn't support 3.13+ yet).

```bash
brew install espeak-ng                  # Spanish (and English fallback) phonemes
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -r requirements.txt
.venv/bin/python -m unidic download     # Japanese dictionary (~500 MB)
```

The LLM model (`qwen2.5:7b`, ~4.7 GB) is downloaded automatically the first time you run `./start.sh`.

## Other ways to run it

### Web server only

```bash
.venv/bin/python web.py                # then open http://localhost:8765 (Ollama must be running)
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
- `llm.py` — translation and explanations via Ollama (or a hosted OpenAI-compatible API such as Groq when `GROQ_API_KEY` / `LLM_API_KEY` is set)
- `word_interpreter.py` — CLI; `web.py` + `static/index.html` — web app
- `start.sh` — one-command start (local or `--public`)
- `Dockerfile`, `prefetch.py` — container image for hosting on a server (not needed for local use; not yet tested)

"""Web interface for the Japanese word pronunciation helper.

Run:
    python web.py            # then open http://localhost:8765
"""

import io
import os
import threading

import requests
import soundfile as sf
from flask import Flask, jsonify, request, send_file, send_from_directory

from word_interpreter import (DEFAULT_MODEL, JA_VOICES, SAMPLE_RATE, analyze,
                              explain, synthesize)

app = Flask(__name__)
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
MODEL = os.environ.get("WORD_INTERPRETER_MODEL", DEFAULT_MODEL)
tts_lock = threading.Lock()  # Kokoro pipeline is shared and not thread-safe


@app.get("/")
def index():
    return send_from_directory(STATIC_DIR, "index.html")


@app.get("/api/interpret")
def interpret():
    word = request.args.get("word", "").strip()
    if not word:
        return jsonify(error="Please enter a word."), 400
    info = analyze(word)
    try:
        info.update(explain(info, MODEL))
    except (requests.ConnectionError, requests.HTTPError) as e:
        info["llm_error"] = f"LLM unavailable ({e.__class__.__name__}). Is `ollama serve` running?"
    info["phrases"] = [
        {"morae": n, "accent": acc, "pattern": pattern, "name": name}
        for n, acc, pattern, name in info["phrases"]
    ]
    return jsonify(info)


@app.get("/api/audio")
def audio():
    word = request.args.get("word", "").strip()
    voice = request.args.get("voice", "jf_alpha")
    if not word or voice not in JA_VOICES:
        return jsonify(error="Bad request."), 400
    speed = 0.7 if request.args.get("slow") == "1" else 1.0
    with tts_lock:
        samples = synthesize(word, voice, speed)
    if samples is None:
        return jsonify(error="No audio produced."), 500
    buf = io.BytesIO()
    sf.write(buf, samples, SAMPLE_RATE, format="WAV")
    buf.seek(0)
    return send_file(buf, mimetype="audio/wav")


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", 8765)))

"""Web interface for Word Interpreter.

Run:
    python web.py            # then open http://localhost:8765
"""

import io
import os
import threading
import time
from collections import defaultdict, deque

from flask import Flask, jsonify, request, send_file, send_from_directory

import speech
from languages import TARGETS, analyze
from llm import DEFAULT_MODEL, LLM_ERRORS, SOURCE_LANGUAGES, error_message, explain, translate

app = Flask(__name__)
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
MODEL = DEFAULT_MODEL

# Public-deployment guards: capped input length, and a per-visitor limit on LLM calls
# so the free LLM quota can't be drained by one person.
MAX_TEXT = int(os.environ.get("MAX_TEXT_LENGTH", 200))
RATE_LIMIT = int(os.environ.get("RATE_LIMIT_PER_MINUTE", 20))
_hits = defaultdict(deque)
_hits_lock = threading.Lock()


def too_many_requests():
    # Behind a hosting proxy, the visitor's IP is the first X-Forwarded-For entry.
    ip = request.headers.get("X-Forwarded-For", request.remote_addr or "").split(",")[0].strip()
    now = time.monotonic()
    with _hits_lock:
        hits = _hits[ip]
        while hits and now - hits[0] > 60:
            hits.popleft()
        if len(hits) >= RATE_LIMIT:
            return True
        hits.append(now)
    return False


def read_text(name, limit=MAX_TEXT):
    text = request.args.get(name, "").strip()
    return text if 0 < len(text) <= limit else None


def llm_error(e):
    return f"LLM unavailable: {error_message(e, MODEL)}."


@app.get("/")
def index():
    return send_from_directory(STATIC_DIR, "index.html")


@app.get("/api/targets")
def targets():
    return jsonify({code: {"name": t["name"], "voices": t["voices"]} for code, t in TARGETS.items()})


@app.get("/api/interpret")
def interpret():
    """Translate (if needed) and analyze the pronunciation."""
    text = read_text("text")
    source = request.args.get("from", "auto")
    target = request.args.get("to", "ja")
    if not text:
        return jsonify(error=f"Please enter a word or phrase (up to {MAX_TEXT} characters)."), 400
    if source not in ("auto", *SOURCE_LANGUAGES) or target not in TARGETS:
        return jsonify(error="Bad language choice."), 400
    if too_many_requests():
        return jsonify(error="Too many requests — please wait a minute."), 429

    result = {"input": text, "source_language": target, "alternatives": []}
    word = text
    try:
        t = translate(text, target, MODEL, source)
        word = t["translation"]
        result.update(source_language=t["source_language"], alternatives=t["alternatives"])
    except LLM_ERRORS as e:
        result["llm_error"] = llm_error(e)

    result.update(analyze(word, target))
    return jsonify(result)


@app.get("/api/explain")
def explain_word():
    word = read_text("word", MAX_TEXT * 2)  # translations can be longer than the input
    target = request.args.get("to", "ja")
    if not word or target not in TARGETS:
        return jsonify(error="Bad request."), 400
    if too_many_requests():
        return jsonify(error="Too many requests — please wait a minute."), 429
    try:
        return jsonify(explain(analyze(word, target), MODEL, target))
    except LLM_ERRORS as e:
        return jsonify(error=llm_error(e)), 502


@app.get("/api/audio")
def audio():
    word = read_text("word", MAX_TEXT * 2)  # translations can be longer than the input
    target = request.args.get("to", "ja")
    voice = request.args.get("voice", "")
    if not word or target not in TARGETS or voice not in TARGETS[target]["voices"]:
        return jsonify(error="Bad request."), 400
    result = speech.synthesize(word, target, voice, slow=request.args.get("slow") == "1")
    if result is None:
        return jsonify(error="No audio produced."), 500
    data, mimetype, _ = result
    return send_file(io.BytesIO(data), mimetype=mimetype)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", 8765)))  # local dev; Docker uses gunicorn

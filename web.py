"""Web interface for Word Interpreter.

Run:
    python web.py            # then open http://localhost:8765
"""

import io
import os

from flask import Flask, jsonify, request, send_file, send_from_directory

import speech
from languages import TARGETS, analyze
from llm import DEFAULT_MODEL, LLM_ERRORS, SOURCE_LANGUAGES, error_message, explain, translate

app = Flask(__name__)
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
MODEL = DEFAULT_MODEL


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
    text = request.args.get("text", "").strip()
    source = request.args.get("from", "auto")
    target = request.args.get("to", "ja")
    if not text:
        return jsonify(error="Please enter a word."), 400
    if source not in ("auto", *SOURCE_LANGUAGES) or target not in TARGETS:
        return jsonify(error="Bad language choice."), 400

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
    word = request.args.get("word", "").strip()
    target = request.args.get("to", "ja")
    if not word or target not in TARGETS:
        return jsonify(error="Bad request."), 400
    try:
        return jsonify(explain(analyze(word, target), MODEL, target))
    except LLM_ERRORS as e:
        return jsonify(error=llm_error(e)), 502


@app.get("/api/audio")
def audio():
    word = request.args.get("word", "").strip()
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
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", 8765)))

"""Speech: Kokoro TTS for Japanese, Mandarin, English and Spanish; edge-tts for Cantonese."""

import asyncio
import io
import logging
import threading

logging.getLogger("jieba").setLevel(logging.WARNING)  # Mandarin G2P is chatty on load

SAMPLE_RATE = 24000
KOKORO_LANG = {"ja": "j", "zh": "z", "en": "a", "es": "e"}

_lock = threading.Lock()  # Kokoro pipelines are shared and not thread-safe
_model = None
_pipelines = {}


def _pipeline(target, with_model):
    """One Kokoro pipeline per language, all sharing a single loaded model."""
    global _model
    key = (target, with_model)
    if key not in _pipelines:
        from kokoro import KModel, KPipeline
        if with_model and _model is None:
            _model = KModel(repo_id="hexgrad/Kokoro-82M").eval()
        _pipelines[key] = KPipeline(lang_code=KOKORO_LANG[target], repo_id="hexgrad/Kokoro-82M",
                                    model=_model if with_model else False)
    return _pipelines[key]


def phonemes(text, target):
    with _lock:
        return " ".join(r.phonemes for r in _pipeline(target, False)(text))


def synthesize(text, target, voice, slow=False):
    """Return (audio bytes, mime type, file extension), or None if nothing was produced."""
    if target == "yue":
        return _edge_tts(text, voice, slow)

    import numpy as np
    import soundfile as sf
    with _lock:
        chunks = [r.audio.numpy() for r in _pipeline(target, True)(text, voice=voice,
                                                                   speed=0.7 if slow else 1.0)
                  if r.audio is not None]
    if not chunks:
        return None
    buf = io.BytesIO()
    sf.write(buf, np.concatenate(chunks), SAMPLE_RATE, format="WAV")
    return buf.getvalue(), "audio/wav", "wav"


def _edge_tts(text, voice, slow):
    import edge_tts

    async def run():
        audio = b""
        async for chunk in edge_tts.Communicate(text, voice, rate="-30%" if slow else "+0%").stream():
            if chunk["type"] == "audio":
                audio += chunk["data"]
        return audio

    audio = asyncio.run(run())
    return (audio, "audio/mpeg", "mp3") if audio else None

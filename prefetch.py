"""Download every model, voice and dictionary ahead of time (run during the Docker build)."""

import warnings

warnings.filterwarnings("ignore")

import speech
from languages import TARGETS, analyze

SAMPLES = {"ja": "東京", "zh": "你好", "yue": "你好", "en": "hello", "es": "hola"}

for target, sample in SAMPLES.items():
    analyze(sample, target)  # dictionaries / phonemizers (OpenJTalk, jieba, spaCy, espeak)
    if target == "yue":
        continue  # edge-tts is an online service; nothing to download
    for voice in TARGETS[target]["voices"]:
        speech.synthesize(sample, target, voice)  # Kokoro model + each voice
    print(f"prefetched {target}")

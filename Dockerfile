FROM python:3.12-slim

# espeak-ng: Spanish/English phonemes. build tools: pyopenjtalk compiles from source.
RUN apt-get update && apt-get install -y --no-install-recommends \
        espeak-ng build-essential cmake \
    && rm -rf /var/lib/apt/lists/*

# Many hosts (e.g. Hugging Face Spaces) run containers as uid 1000.
RUN useradd -m -u 1000 app
USER app
ENV HOME=/home/app \
    PATH=/home/app/.local/bin:$PATH \
    HF_HOME=/home/app/.cache/huggingface \
    PYTHONUNBUFFERED=1
WORKDIR /home/app/src

# CPU-only PyTorch keeps the image far smaller than the default CUDA build.
RUN pip install --no-cache-dir --user torch --index-url https://download.pytorch.org/whl/cpu
COPY --chown=app requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt gunicorn \
    && python -m unidic download

COPY --chown=app . .
RUN python prefetch.py

# Hugging Face Spaces expects 7860; Cloud Run and others set PORT themselves.
ENV PORT=7860
EXPOSE 7860
CMD gunicorn web:app --bind 0.0.0.0:$PORT --workers 1 --threads 8 --timeout 300

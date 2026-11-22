#!/usr/bin/env bash
# Start Word Interpreter: Ollama (if needed), the web server, and your browser.
#
#   ./start.sh            # open http://localhost:8765 on this computer
#   ./start.sh --public   # also print a temporary public link (Cloudflare Quick Tunnel)
#
# Press Ctrl+C to stop. Everything this script started is shut down.

set -euo pipefail
cd "$(dirname "$0")"

PORT="${PORT:-8765}"
MODEL="${WORD_INTERPRETER_MODEL:-qwen2.5:7b}"
URL="http://localhost:$PORT"
LOG_DIR="$(mktemp -d)"
PUBLIC=false
[[ "${1:-}" == "--public" ]] && PUBLIC=true

started=()
cleanup() {
  if [[ -n "${started[*]-}" ]]; then echo; echo "Stopping..."; fi
  for pid in ${started[@]+"${started[@]}"}; do kill "$pid" 2>/dev/null || true; done
  rm -rf "$LOG_DIR"
}
trap cleanup EXIT
trap 'exit 130' INT TERM  # Ctrl+C or kill: exit, which runs cleanup

wait_for() {  # wait_for <url> <seconds>
  for _ in $(seq 1 $(($2 * 2))); do
    curl -s -o /dev/null "$1" && return 0
    sleep 0.5
  done
  return 1
}

# 1. Checks
if [[ ! -x .venv/bin/python ]]; then
  echo "Python environment not found. Follow the Setup steps in README.md first."
  exit 1
fi
if curl -s -o /dev/null "$URL"; then
  echo "Something is already running on port $PORT. Stop it, or run: PORT=8766 ./start.sh"
  exit 1
fi
if $PUBLIC && ! command -v cloudflared >/dev/null; then
  echo "--public needs cloudflared. Install it with: brew install cloudflared"
  exit 1
fi

# 2. Ollama (the local LLM) — skipped if a hosted LLM API key is set
if [[ -z "${LLM_API_KEY:-}${GROQ_API_KEY:-}" ]]; then
  if ! curl -s -o /dev/null http://localhost:11434/api/tags; then
    if ! command -v ollama >/dev/null; then
      echo "Ollama not found. Install it from https://ollama.com (or set GROQ_API_KEY)."
      exit 1
    fi
    echo "Starting Ollama..."
    ollama serve > "$LOG_DIR/ollama.log" 2>&1 &
    started+=($!)
    wait_for http://localhost:11434/api/tags 30 || { echo "Ollama didn't start:"; cat "$LOG_DIR/ollama.log"; exit 1; }
  fi
  if ! grep -q "^$MODEL" <<< "$(ollama list)"; then
    echo "Downloading $MODEL (one time)..."
    ollama pull "$MODEL"
  fi
fi

# 3. Web server
echo "Starting the web server..."
PORT="$PORT" .venv/bin/python web.py > "$LOG_DIR/web.log" 2>&1 &
started+=($!)
wait_for "$URL" 60 || { echo "Web server didn't start:"; cat "$LOG_DIR/web.log"; exit 1; }

# 4. Public link (optional)
if $PUBLIC; then
  echo "Opening a public tunnel..."
  cloudflared tunnel --url "$URL" > "$LOG_DIR/tunnel.log" 2>&1 &
  started+=($!)
  public_url=""
  for _ in $(seq 1 60); do
    public_url=$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' "$LOG_DIR/tunnel.log" | head -1 || true)
    [[ -n "$public_url" ]] && break
    sleep 0.5
  done
  [[ -n "$public_url" ]] || { echo "Tunnel didn't start:"; cat "$LOG_DIR/tunnel.log"; exit 1; }
fi

# 5. Open the browser
if command -v open >/dev/null; then open "$URL"; elif command -v xdg-open >/dev/null; then xdg-open "$URL"; fi

echo
echo "  Word Interpreter is running"
echo "  On this computer : $URL"
$PUBLIC && echo "  Public link      : $public_url   (anyone with this link can use it)"
echo
echo "  Press Ctrl+C to stop."
wait "${started[@]: -1}"

#!/bin/bash
# scripts/start-backend.sh
# Starts the VeeTrack FastAPI backend.
# Always run from the monorepo root: bash scripts/start-backend.sh

set -e
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$ROOT_DIR/veetrack-backend"

echo "=== VeeTrack Backend ==="
cd "$BACKEND_DIR"

# Create venv if missing
if [ ! -f "venv/bin/activate" ]; then
  echo "Creating Python virtual environment..."
  python3 -m venv venv
fi
source venv/bin/activate

# Load root .env into environment
if [ -f "$ROOT_DIR/.env" ]; then
  export $(grep -v '^#' "$ROOT_DIR/.env" | xargs) 2>/dev/null || true
fi

# Install dependencies from root requirements.txt
echo "Installing Python dependencies..."
pip install -r "$ROOT_DIR/requirements.txt" --quiet

# spaCy model (try transformer first, fall back to sm)
echo "Checking spaCy model..."
python3 -c "import spacy; spacy.load('en_core_web_trf')" 2>/dev/null || \
  python3 -m spacy download en_core_web_trf 2>/dev/null || \
  python3 -m spacy download en_core_web_sm

# NLTK data
echo "Checking NLTK data..."
python3 -c "
import nltk
nltk.download('punkt', quiet=True)
nltk.download('punkt_tab', quiet=True)
nltk.download('stopwords', quiet=True)
" 2>/dev/null || true

# Ollama / llama3.2
echo "Checking Ollama..."
if command -v ollama &>/dev/null; then
  ollama list 2>/dev/null | grep -q "llama3.2" || ollama pull llama3.2
  pgrep -x ollama >/dev/null 2>&1 || (ollama serve &>/tmp/ollama.log & sleep 2)
  echo "Ollama ready (llama3.2) ✓"
else
  echo "WARNING: Ollama not found. Chat falls back to context extraction."
  echo "         Install: curl -fsSL https://ollama.com/install.sh | sh"
fi

echo "Starting FastAPI on http://localhost:8000..."
export PYTHONPATH="$BACKEND_DIR"
uvicorn main:app --host 0.0.0.0 --port 8000 --reload --log-level info

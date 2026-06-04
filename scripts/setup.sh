#!/bin/bash
# scripts/setup.sh
# One-time system setup for VeeTrack.
# Run once after cloning the repo.

set -e
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "=== VeeTrack One-Time Setup ==="
echo ""

# ── SQLite & DiskCache (No external broker needed) ─────────────
echo "[1/4] Checking Database / Cache..."
echo "Using SQLite and DiskCache natively. No Redis required ✓"

# ── Ollama + llama3.2 ──────────────────────────────────────
echo ""
echo "[2/4] Checking Ollama..."
if ! command -v ollama &>/dev/null; then
  echo "Installing Ollama..."
  curl -fsSL https://ollama.com/install.sh | sh
fi
ollama list 2>/dev/null | grep -q "llama3.2" || ollama pull llama3.2
echo "Ollama + llama3.2 ✓"

# ── Python venv + dependencies ─────────────────────────────────
echo ""
echo "[3/4] Setting up Python environment..."
cd "$ROOT_DIR/veetrack-backend"
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip --quiet
pip install -r "$ROOT_DIR/requirements.txt" --quiet
python3 -m spacy download en_core_web_trf 2>/dev/null || python3 -m spacy download en_core_web_sm
python3 -c "
import nltk
nltk.download('punkt', quiet=True)
nltk.download('punkt_tab', quiet=True)
nltk.download('stopwords', quiet=True)
"
echo "Python environment ✓"

# ── Node.js frontend ───────────────────────────────────────────
echo ""
echo "[4/4] Setting up frontend..."
cd "$ROOT_DIR/veetrack-frontend"
npm install --silent
echo "Frontend ✓"

echo ""
echo "=== Setup complete! ==="
echo "Start the app with: npm run dev:all"
echo "From the root directory: $ROOT_DIR"

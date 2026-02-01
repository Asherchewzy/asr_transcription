#!/usr/bin/env bash
set -euo pipefail

echo "==== Setting up development environment ===="

# Check and install uv
if command -v uv >/dev/null 2>&1; then
  echo "✓ uv is already installed"
else
  echo "uv is not installed. Attempting to install via official script..."
  if command -v curl >/dev/null 2>&1; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
  elif command -v wget >/dev/null 2>&1; then
    wget -qO- https://astral.sh/uv/install.sh | sh
  else
    echo "Neither curl nor wget is available. Please install uv manually:"
    echo "https://docs.astral.sh/uv/getting-started/installation/"
    exit 1
  fi
fi

# Check if Homebrew is available
HAS_BREW=false
if command -v brew >/dev/null 2>&1; then
  HAS_BREW=true
  echo "✓ Homebrew is installed - will auto-install missing dependencies"
else
  echo "! Homebrew not found - will show manual installation instructions if needed"
fi

# Check for FFmpeg
if command -v ffmpeg >/dev/null 2>&1; then
  echo "✓ FFmpeg is already installed"
else
  if [ "$HAS_BREW" = true ]; then
    echo "Installing FFmpeg via Homebrew..."
    brew install ffmpeg
  else
    echo "WARNING: ffmpeg not found. Install it with: brew install ffmpeg"
  fi
fi

# Check for Node.js and npm
if command -v node >/dev/null 2>&1 && command -v npm >/dev/null 2>&1; then
  echo "✓ Node.js and npm are already installed ($(node --version), npm $(npm --version))"
else
  if [ "$HAS_BREW" = true ]; then
    echo "Installing Node.js via Homebrew..."
    brew install node
  else
    echo "WARNING: Node.js/npm not found. Install it with: brew install node"
  fi
fi

echo ""
echo "==== Setting up Python environment ===="
uv python install 3.11.14

cd "$(dirname "$0")/backend"
echo "Installing backend dependencies..."
uv sync --extra dev
echo "Backend dependencies installed"

cd ..

echo ""
echo "==== Setting up Frontend environment ===="
cd frontend
if command -v npm >/dev/null 2>&1; then
  echo "Installing frontend dependencies from package-lock.json..."
  npm ci
  echo "Frontend dependencies installed (exact versions)"
else
  echo "ERROR: npm not found. Skipping frontend setup."
  echo "Install Node.js with: brew install node"
fi

cd ..

echo ""
echo "==== Setup complete ===="


#!/usr/bin/env bash
# setup.sh — hand_exo environment setup
# Author: S. Sasmitha
set -e

echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║  hand_exo — Hand Exoskeleton Sorting Game               ║"
echo "║  Author : S. Sasmitha                                    ║"
echo "║  Repo   : github.com/sasmitha/hand_exo                  ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""

PY=$(command -v python3 || command -v python)

# Virtual environment
if [ ! -d ".venv" ]; then
  echo "→  Creating virtual environment …"
  $PY -m venv .venv
fi
source .venv/bin/activate
pip install --upgrade pip -q

# Python deps
echo "→  Installing Python dependencies …"
pip install -r requirements.txt -q
echo "   ✅  Python packages ready"

# Vosk model
MODEL="vosk-model-small-en-us-0.15"
if [ ! -d "$MODEL" ]; then
  echo "→  Downloading Vosk speech model (~40 MB) …"
  wget -q "https://alphacephei.com/vosk/models/${MODEL}.zip" -O _vosk.zip
  unzip -q _vosk.zip && rm _vosk.zip
  echo "   ✅  Vosk model ready"
else
  echo "→  Vosk model already present"
fi

# MySQL instructions
echo ""
echo "→  MySQL setup (run once as root):"
echo ""
echo "     CREATE DATABASE IF NOT EXISTS rehab_db;"
echo "     CREATE USER IF NOT EXISTS 'rehab_user'@'localhost'"
echo "       IDENTIFIED BY 'rehab_pass';"
echo "     GRANT ALL PRIVILEGES ON rehab_db.* TO 'rehab_user'@'localhost';"
echo "     FLUSH PRIVILEGES;"
echo ""

# Output dirs
mkdir -p reports

echo "╔══════════════════════════════════════════════════════════╗"
echo "║  Setup complete! Quick-start commands:                   ║"
echo "║                                                          ║"
echo "║  source .venv/bin/activate                               ║"
echo "║                                                          ║"
echo "║  python main.py demo              # no hardware needed   ║"
echo "║  python main.py calibrate         # camera calibration   ║"
echo "║  python main.py game --player Me  # full VISION mode     ║"
echo "║  python main.py game --player Me --mode GLOVE            ║"
echo "║  python main.py dashboard --player Me                    ║"
echo "║  python main.py report --player Me                       ║"
echo "║  python main.py evaluate          # reproduce Table I    ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""

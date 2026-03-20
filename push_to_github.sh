#!/usr/bin/env bash
# push_to_github.sh
# Initialises git, makes the first commit, and pushes to sasmitha/hand_exo
#
# Usage:
#   bash push_to_github.sh                     # uses gh CLI (recommended)
#   GITHUB_TOKEN=ghp_xxx bash push_to_github.sh  # token fallback

set -e

GITHUB_USER="sasmitha"
REPO_NAME="hand_exo"
REMOTE="https://github.com/${GITHUB_USER}/${REPO_NAME}.git"

echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║  Pushing hand_exo → github.com/sasmitha/hand_exo        ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""

# ── 1. Git init ───────────────────────────────────────────────────────────────
if [ ! -d ".git" ]; then
  git init
  git branch -M main
fi

# ── 2. Stage everything ───────────────────────────────────────────────────────
git add -A

# ── 3. Commit ─────────────────────────────────────────────────────────────────
git commit -m "feat: initial release v1.0.0

Hand Exoskeleton Sorting Game — S. Sasmitha
Amrita School of Artificial Intelligence, Coimbatore
Amrita Vishwa Vidyapeetham, India

IEEE Conference Paper 2025:
  'Development of an Intelligent Sorting Game with Real-Time
   Hand Gesture Control and MySQL Performance Analytics'

System components:
  - MediaPipe gesture recognition    (F1 92.85%)
  - OpenCV CSRT object tracker       (95.8% frame coverage)
  - PyGame sorting game              (60 FPS, adaptive difficulty)
  - Arduino C++ glove firmware       (5x MG996R, 12.4N peak force)
  - Vosk offline voice control       (open/close/stop)
  - MySQL session analytics          (3-tier adaptive feedback)
  - 8-channel sEMG analysis          (~3x voluntary/actuated RMS ratio)
  - 49 unit tests, CI on 3.9/3.10/3.11
  - Interactive HTML results viewer"

# ── 4. Push ───────────────────────────────────────────────────────────────────
if command -v gh &>/dev/null; then
  echo "→  Using GitHub CLI …"
  # Create repo if it doesn't exist, then push
  gh repo create "${GITHUB_USER}/${REPO_NAME}" \
    --public \
    --description "Hand Exoskeleton Sorting Game — Real-Time Gesture Control & MySQL Analytics" \
    --homepage "https://github.com/${GITHUB_USER}/${REPO_NAME}" \
    2>/dev/null || true
  git remote remove origin 2>/dev/null || true
  git remote add origin "${REMOTE}"
  git push -u origin main

elif [ -n "$GITHUB_TOKEN" ]; then
  echo "→  Using GITHUB_TOKEN …"
  AUTHED="https://${GITHUB_TOKEN}@github.com/${GITHUB_USER}/${REPO_NAME}.git"
  git remote remove origin 2>/dev/null || true
  git remote add origin "$AUTHED"
  git push -u origin main

else
  echo "→  No gh CLI or GITHUB_TOKEN found."
  echo "   Adding remote manually — enter your credentials when prompted:"
  git remote remove origin 2>/dev/null || true
  git remote add origin "${REMOTE}"
  git push -u origin main
fi

echo ""
echo "✅  Done!  https://github.com/${GITHUB_USER}/${REPO_NAME}"
echo ""

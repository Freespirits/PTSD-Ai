#!/usr/bin/env bash
# =============================================================================
# Bootstrap script - initializes git and pushes to a fresh GitHub repo
#
# Prerequisites:
#   - `gh` CLI installed and authenticated (https://cli.github.com/)
#   - You're in the project root
#
# Usage:
#   ./scripts/init-github.sh <github-username-or-org> [--public]
# =============================================================================

set -euo pipefail

if [ $# -lt 1 ]; then
  echo "Usage: $0 <github-username-or-org> [--public]"
  exit 1
fi

OWNER="$1"
VISIBILITY="${2:-private}"
REPO_NAME="PTSD-Ai"

if [ "$VISIBILITY" = "--public" ]; then
  VISIBILITY_FLAG="--public"
else
  VISIBILITY_FLAG="--private"
fi

if ! command -v gh &> /dev/null; then
  echo "❌ gh CLI not found. Install from https://cli.github.com/"
  exit 1
fi

if [ -d ".git" ]; then
  echo "⚠️  .git already exists. Skipping git init."
else
  echo "📦 Initializing git repo..."
  git init -b main
fi

echo "📝 Staging files..."
git add .

if git diff --cached --quiet; then
  echo "⚠️  Nothing to commit."
else
  git commit -m "Initial scaffold: Hebrew voice RAG for PTSD support

- LiveKit voice agent with VAD/STT/LLM/TTS pipeline
- Hebrew safety layer with crisis detection + hotline escalation
- RAG over article corpus with Qdrant + multilingual embeddings
- Ingestion pipeline for PDF/DOCX/MD/TXT/HTML + URL scraping
- Web client (WebRTC) + Twilio phone gateway setup
- Docker Compose for local dev, Terraform starter for AWS Tel Aviv
- Comprehensive safety & deployment docs
"
fi

echo "🐙 Creating GitHub repo ${OWNER}/${REPO_NAME}..."
gh repo create "${OWNER}/${REPO_NAME}" \
  ${VISIBILITY_FLAG} \
  --description "Hebrew voice RAG agent for PTSD support (military trauma focus)" \
  --source=. \
  --remote=origin \
  --push

echo ""
echo "✅ Done!"
echo "   Repo: https://github.com/${OWNER}/${REPO_NAME}"
echo ""
echo "Next steps:"
echo "  1. cp .env.example .env  # and fill in your API keys"
echo "  2. docker-compose up -d qdrant"
echo "  3. Place articles in data/articles/ and run:"
echo "     python -m ingestion.ingest"
echo "  4. Run the agent:"
echo "     python -m agent.main dev"

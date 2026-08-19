#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -ne 1 ]; then
  echo "Usage: $0 https://github.com/YOUR-USERNAME/cafa-ivr.git"
  exit 1
fi

REMOTE="$1"

git init
git add .
git commit -m "Release CAFA-IVR v1.0.0"
git branch -M main
git remote add origin "$REMOTE"
git push -u origin main

echo "Published CAFA-IVR to $REMOTE"

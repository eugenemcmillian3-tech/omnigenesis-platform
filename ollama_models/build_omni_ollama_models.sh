#!/usr/bin/env bash
# OMNIGENESIS-Ω 5th-Paradigm Local Ollama Constellation Builder (Tier B: Balanced Workstation / GPU Server (8 GB – 16 GB+ VRAM/RAM))
set -euo pipefail

echo "[1/3] Pulling base small models from Ollama registry..."
ollama pull deepseek-r1:1.5b
ollama pull deepseek-r1:7b
ollama pull llama3.2:3b
ollama pull phi3.5:3.8b
ollama pull qwen2.5-coder:3b

echo "[2/3] Building custom OMNIGENESIS-Ω 5th-Paradigm models from Modelfiles..."
ollama create omni-manifest-coder:latest -f Modelfile.omni-manifest-coder
ollama create omni-isomorph-agi:latest -f Modelfile.omni-isomorph-agi
ollama create omni-swarm-asi:latest -f Modelfile.omni-swarm-asi
ollama create omni-lyapunov-prover:latest -f Modelfile.omni-lyapunov-prover
ollama create omnigenesis-omega:latest -f Modelfile.omnigenesis-omega

echo "[3/3] Verifying installed OMNIGENESIS-Ω constellation..."
ollama list | grep -E "omni-|omnigenesis-" || true
echo "✓ All 5 OMNIGENESIS-Ω 5th-Paradigm models ready! Run: ollama run omnigenesis-omega:latest"

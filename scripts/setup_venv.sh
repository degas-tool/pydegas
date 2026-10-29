#!/usr/bin/env bash
# Installs the artifact without Docker (e.g. on the TACAS VM, Ubuntu, amd64 or
# arm64). Needs network access. Python 3.12 (the version the artifact was
# tested with) is used if present, otherwise uv downloads it, so a newer system
# Python, e.g. 3.14, is not used. Afterwards run:
#   source libs/pydegas/.venv/bin/activate
set -euo pipefail
cd "$(dirname "$0")/.."

export PATH="$PWD/.uv-bin:$PATH"
if ! command -v uv > /dev/null; then
  echo "installing uv 0.13.5 into .uv-bin"
  curl -LsSf https://astral.sh/uv/0.13.5/install.sh | UV_UNMANAGED_INSTALL="$PWD/.uv-bin" sh
fi

cd libs/pydegas
uv sync --frozen --python 3.12           # exact versions of uv.lock, CPU-only PyTorch
uv pip install matplotlib==3.11.2        # needed by the reference implementation
echo "Installed. Activate with: source libs/pydegas/.venv/bin/activate"

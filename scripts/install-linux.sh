#!/usr/bin/env bash
# Reproduce the verified Python 3.12 Linux CPU development environment.
set -euo pipefail
cd "$(dirname "$0")/.."
export PIP_CACHE_DIR="$PWD/explore/pip-cache"
python3 -c 'import sys; assert sys.version_info[:2] == (3, 12), "Python 3.12 is required"'
if [ ! -x .venv/bin/python ]; then
  python3 -m venv .venv
fi
.venv/bin/python -c 'import sys; assert sys.version_info[:2] == (3, 12)'
.venv/bin/python -m pip install --disable-pip-version-check --require-hashes \
  --extra-index-url https://download.pytorch.org/whl/cpu \
  -r requirements/phase1-linux.txt
.venv/bin/python -m pip install --no-deps --no-build-isolation -e '.[dev]'
.venv/bin/python -m pip check
.venv/bin/python -c 'import torch, torchvision; assert torch.version.cuda is None; print("CPU dependencies:", torch.__version__, torchvision.__version__)'

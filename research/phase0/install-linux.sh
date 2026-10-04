#!/usr/bin/env bash
# Tested cloud setup; Windows setup remains a separate acceptance check.
set -euo pipefail
cd "$(dirname "$0")/../.."
python3 -c 'import sys; assert sys.version_info[:2] == (3, 12), "Python 3.12 is required"'
if [ ! -x .venv/bin/python ]; then
  python3 -m venv .venv
fi
.venv/bin/python -c 'import sys; assert sys.version_info[:2] == (3, 12)'
.venv/bin/python -m pip install --disable-pip-version-check --require-hashes \
  --extra-index-url https://download.pytorch.org/whl/cpu \
  -r research/phase0/requirements-linux.txt
.venv/bin/python -m pip check
.venv/bin/python -c 'import torch, torchvision; from docling.document_converter import DocumentConverter; print("CPU dependencies:", torch.__version__, torchvision.__version__)'

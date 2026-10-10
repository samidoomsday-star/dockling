#!/usr/bin/env bash
# Linux x86_64 Python 3.12 only. No model download or public deployment.
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -c 'import platform,sys; assert sys.platform=="linux" and sys.version_info[:2]==(3,12) and platform.machine()=="x86_64", "This hash lock needs Linux x86_64 Python 3.12"'
node -e 'if(+process.versions.node.split(".")[0]!==24 || +process.versions.node.split(".")[1]<15)throw Error("Node 24.15+ (24.x) is required")'
docker info >/dev/null
docker compose version >/dev/null
python3 scripts/saas-local.py init
bash scripts/install-linux.sh
.venv/bin/python -m pip install --require-hashes -r requirements/saas-linux.txt
.venv/bin/python -m pip check
npm ci --prefix frontend --cache "$PWD/.local-saas/npm-cache"
npm run build:api --prefix frontend
.venv/bin/python scripts/saas-local.py setup

#!/bin/sh
set -eu
APP_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$APP_DIR"
.venv/bin/python -c 'import sys; assert sys.version_info[:2] == (3,11), "Linux 发行包需要使用项目 Python 3.11 构建"'
.venv/bin/python linux_pet.py --qa-only
QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest tools.test_linux_port tools.test_state_audit tools.test_compressed_rollout tools.test_internal_memory -q
PYINSTALLER_CONFIG_DIR="$APP_DIR/.uv-cache/pyinstaller" .venv/bin/python -m PyInstaller --noconfirm --clean linux_pet.spec
.venv/bin/python tools/package_linux.py

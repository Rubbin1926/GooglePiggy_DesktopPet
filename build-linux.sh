#!/bin/sh
set -eu
APP_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$APP_DIR"
.venv/bin/python -c 'import sys; assert sys.version_info[:2] == (3,10), "Linux 发行包需要使用 Ubuntu 22.04 的 Python 3.10 构建"'
.venv/bin/python linux_pet.py --qa-only
PYINSTALLER_CONFIG_DIR="$APP_DIR/.uv-cache/pyinstaller" .venv/bin/python -m PyInstaller --noconfirm --clean linux_pet.spec
.venv/bin/python tools/package_linux.py

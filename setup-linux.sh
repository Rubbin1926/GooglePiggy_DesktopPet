#!/bin/sh
set -eu
APP_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$APP_DIR"
./install-deps-linux.sh --source
PYTHON_VERSION=$(/usr/bin/python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])')
case "$PYTHON_VERSION" in
    3.10|3.12) ;;
    *) echo '请使用 Ubuntu 22.04 自带的 Python 3.10 或 Ubuntu 24.04 自带的 Python 3.12。' >&2; exit 1 ;;
esac
if [ -e .venv ] || [ -L .venv ]; then
    if ! .venv/bin/python -c 'import sys; sys.exit(("%d.%d" % sys.version_info[:2]) != sys.argv[1])' "$PYTHON_VERSION"; then
        echo "现有 .venv 与系统 Python $PYTHON_VERSION 不匹配或已损坏；请先将旧 .venv 移走或改名，再运行安装脚本。" >&2
        exit 1
    fi
else
    /usr/bin/python3 -m venv .venv
fi
.venv/bin/python -m pip install --disable-pip-version-check --upgrade pip
.venv/bin/python -m pip install --disable-pip-version-check --only-binary=:all: -r requirements-linux.lock
.venv/bin/python linux_pet.py --qa-only
echo "系统 Python $PYTHON_VERSION 的项目环境已配置。请在 Xorg 会话运行 ./start-linux.sh，或 ./install-linux.sh 登记应用入口和 Hook。"

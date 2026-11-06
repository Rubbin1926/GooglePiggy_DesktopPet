#!/bin/sh
set -eu
APP_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
if [ -x "$APP_DIR/googlepiggy" ] && [ ! -f "$APP_DIR/linux_pet.py" ]; then
    exec "$APP_DIR/googlepiggy" "$@"
fi
if [ ! -x "$APP_DIR/.venv/bin/python" ]; then
    echo '请先运行 ./setup-linux.sh，使用本机 Ubuntu 自带的 Python 创建项目环境。' >&2
    exit 1
fi
exec "$APP_DIR/.venv/bin/python" "$APP_DIR/linux_pet.py" "$@"

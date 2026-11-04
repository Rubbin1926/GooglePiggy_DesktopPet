#!/bin/sh
set -eu
APP_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
if [ -x "$APP_DIR/googlepiggy" ]; then
    exec "$APP_DIR/googlepiggy" "$@"
fi
if [ ! -x "$APP_DIR/.venv/bin/python" ]; then
    echo '请先运行 ./setup-linux.sh 创建 Python 3.10 虚拟环境。' >&2
    exit 1
fi
exec "$APP_DIR/.venv/bin/python" "$APP_DIR/linux_pet.py" "$@"

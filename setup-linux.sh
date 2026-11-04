#!/bin/sh
set -eu
APP_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$APP_DIR"
./install-deps-linux.sh --source
/usr/bin/python3 -c 'import sys; assert sys.version_info[:2] == (3,10), "此安装脚本以 Ubuntu 22.04 自带的 Python 3.10 为基线。"'
if [ -x .venv/bin/python ]; then
    .venv/bin/python -c 'import sys; assert sys.version_info[:2] == (3,10), "现有 .venv 不是 Python 3.10；请先将旧 .venv 移走或改名，再运行安装脚本。"'
else
    /usr/bin/python3 -m venv .venv
fi
.venv/bin/python -m pip install --disable-pip-version-check --upgrade pip
.venv/bin/python -m pip install --disable-pip-version-check -r requirements-linux.lock
.venv/bin/python linux_pet.py --qa-only
echo 'Python 3.10 环境已配置。运行 ./start-linux.sh，或 ./install-linux.sh 登记应用入口和 Hook。'

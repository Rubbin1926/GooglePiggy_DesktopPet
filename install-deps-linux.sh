#!/bin/sh
# Standard Ubuntu packages for the GUI; --source also adds Python's venv support.
set -eu
APP_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
case "${1:-}" in
    '') SOURCE_PACKAGES='' ;;
    --source) SOURCE_PACKAGES='python3 python3-venv' ;;
    *) echo '用法：./install-deps-linux.sh [--source]' >&2; exit 2 ;;
esac
MISSING_PACKAGES=''
for package in $(cat "$APP_DIR/requirements-linux-apt.txt") $SOURCE_PACKAGES; do
    if [ "$(dpkg-query -W -f='${Status}' "$package" 2>/dev/null || true)" != 'install ok installed' ]; then
        MISSING_PACKAGES="$MISSING_PACKAGES $package"
    fi
done
if [ -n "$MISSING_PACKAGES" ]; then
    echo "安装 Ubuntu 运行依赖：$MISSING_PACKAGES"
    if [ "$(id -u)" -eq 0 ]; then
        apt-get update
        apt-get install -y --no-install-recommends $MISSING_PACKAGES
    else
        sudo apt-get update
        sudo apt-get install -y --no-install-recommends $MISSING_PACKAGES
    fi
fi

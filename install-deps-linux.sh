#!/bin/sh
# Standard Ubuntu packages for the GUI; --source also adds Python's venv support.
set -eu
APP_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
case "${1:-}" in
    '') SOURCE_PACKAGES='' ;;
    --source) SOURCE_PACKAGES='python3 python3-venv' ;;
    *) echo '用法：./install-deps-linux.sh [--source]' >&2; exit 2 ;;
esac
GLIB_PACKAGE=libglib2.0-0
if [ -r /etc/os-release ]; then
    . /etc/os-release
    if [ "${ID:-}" = ubuntu ] && [ "${VERSION_ID:-}" = 24.04 ]; then
        GLIB_PACKAGE=libglib2.0-0t64
    fi
fi
MISSING_PACKAGES=''
NATIVE_ARCH=$(dpkg --print-architecture)
for package in $(cat "$APP_DIR/requirements-linux-apt.txt") $SOURCE_PACKAGES; do
    if [ "$package" = libglib2.0-0 ]; then
        package=$GLIB_PACKAGE
    fi
    if ! dpkg-query -W -f='${Architecture} ${Status}\n' "$package" 2>/dev/null |
         grep -Eq "^(all|$NATIVE_ARCH) install ok installed$"; then
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

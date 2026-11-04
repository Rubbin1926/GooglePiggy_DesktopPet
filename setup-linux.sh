#!/bin/sh
# Everything downloaded by this script stays inside this project directory.
set -eu
APP_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$APP_DIR"
export UV_CACHE_DIR="$APP_DIR/.uv-cache"
export UV_PYTHON_INSTALL_DIR="$APP_DIR/.runtime/python"
UV="$APP_DIR/.tools/uv/bin/uv"
if [ ! -x "$UV" ]; then
    python3 - <<'PY'
import hashlib, io, json, platform, urllib.request, zipfile
from pathlib import Path
if platform.system() != 'Linux' or platform.machine() != 'x86_64':
    raise SystemExit('此安装脚本面向 Ubuntu x86_64。')
with urllib.request.urlopen('https://pypi.org/pypi/uv/0.13.7/json', timeout=30) as response:
    metadata = json.load(response)
wheel = next(f for f in metadata['urls'] if f['filename'].endswith('.whl') and 'manylinux_2_17_x86_64' in f['filename'])
with urllib.request.urlopen(wheel['url'], timeout=60) as response:
    data = response.read()
if hashlib.sha256(data).hexdigest() != '2c9bdc4a872b60a93c5f26c0791089ea11585a4f9d3b3c017d78eb8487505e25':
    raise SystemExit('uv 下载校验失败，未执行。')
root = Path('.tools/uv')
with zipfile.ZipFile(io.BytesIO(data)) as archive:
    for name in archive.namelist():
        if name.endswith('.data/scripts/uv'):
            target = root/'bin/uv'
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.read(name))
            target.chmod(0o755)
print('uv 已校验并安装到项目目录。')
PY
fi
if [ -x .venv/bin/python ]; then
    .venv/bin/python -c 'import sys; assert sys.version_info[:2] == (3,11), "现有 .venv 不是 Python 3.11；请先另行保留该环境。"'
else
    "$UV" python install 3.11 --no-bin --no-config
    "$UV" venv .venv --python 3.11 --seed --no-config
fi
"$UV" pip sync requirements-linux.lock --python .venv/bin/python --no-config
if ! .venv/bin/python -c 'import ctypes; ctypes.CDLL("libxcb-cursor.so.0")' 2>/dev/null; then
    mkdir -p .uv-cache/native-debs
    (cd .uv-cache/native-debs && apt-get download libxcb-cursor0)
    for package in .uv-cache/native-debs/libxcb-cursor0_*.deb; do
        dpkg-deb -x "$package" .native
    done
fi
if [ ! -f /usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc ] && [ ! -f .native/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc ]; then
    mkdir -p .uv-cache/native-debs
    (cd .uv-cache/native-debs && apt-get download fonts-noto-cjk)
    for package in .uv-cache/native-debs/fonts-noto-cjk_*.deb; do
        dpkg-deb -x "$package" .native
    done
fi
.venv/bin/python linux_pet.py --qa-only
echo '独立 Python 3.11 已配置。运行 ./start-linux.sh，或 ./install-linux.sh 登记应用入口和 Hook。'

#!/bin/sh
# Downloads and installs the public Release in an otherwise fresh Ubuntu image.
set -eu
docker run --rm -i ubuntu:22.04 /bin/bash -se <<'CONTAINER'
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
# Download tools and a test display; Xvfb is not an application dependency.
apt-get install -y --no-install-recommends python3 ca-certificates sudo xvfb xauth
useradd --create-home --shell /bin/bash piggytest
printf 'piggytest ALL=(ALL) NOPASSWD: ALL\n' > /etc/sudoers.d/piggytest
chmod 440 /etc/sudoers.d/piggytest
cat > /tmp/check-release.py <<'PY'
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import sys
import tarfile
import time
import urllib.request

assert sys.version_info[:2] == (3, 10)
root = Path.home()/'GooglePiggy'
root.mkdir()
url = 'https://api.github.com/repos/Rubbin1926/GooglePiggy_DesktopPet/releases/tags/v0.5.9-linux'
request = urllib.request.Request(url+'?check='+str(time.time_ns()), headers={'User-Agent': 'GooglePiggy-release-smoke', 'Cache-Control': 'no-cache'})
with urllib.request.urlopen(request, timeout=30) as response:
    release = json.load(response)
assets = {asset['name']: asset for asset in release['assets']}
name = 'GooglePiggy-0.5.9-linux-x86_64.tar.gz'
for filename in (name, 'SHA256SUMS.txt'):
    urllib.request.urlretrieve(assets[filename]['browser_download_url']+'?check='+str(time.time_ns()), root/filename)
expected = next(line.split()[0] for line in (root/'SHA256SUMS.txt').read_text().splitlines() if line.split()[-1] == name)
checksum = hashlib.sha256()
with (root/name).open('rb') as stream:
    while chunk := stream.read(1024*1024):
        checksum.update(chunk)
assert checksum.hexdigest() == expected
with tarfile.open(root/name, 'r:gz') as archive:
    for member in archive.getmembers():
        path = PurePosixPath(member.name)
        assert not path.is_absolute() and '..' not in path.parts
        assert member.isfile() or member.isdir()
    archive.extractall(root)
subprocess.run(['./install-deps-linux.sh'], cwd=root, check=True)
subprocess.run(['./install-linux.sh', '--no-hooks'], cwd=root, check=True)
assert (Path.home()/'.local/share/applications/googlepiggy-linux.desktop').is_file()
assert (Path.home()/'.config/autostart/googlepiggy-linux.desktop').is_file()
result = subprocess.run(['./googlepiggy', '--qa-only'], cwd=root, capture_output=True, text=True, check=True)
info = json.loads(result.stdout)
assert info['frozen'] and info['python'].startswith('3.10.') and info['frames'] == 2167
state = root/'smoke-state'
subprocess.run(['xvfb-run', '-a', './start-linux.sh', '--state-dir', str(state), '--no-observe', '--no-update-check', '--quit-after', '2'], cwd=root, check=True, timeout=15)
heartbeat = json.loads((state/'pig-heartbeat.json').read_text())
assert heartbeat['platform'] == 'xcb' and heartbeat['window_visible']
print(json.dumps({'release_install': 'passed', 'system_python': sys.version.split()[0], 'runtime': info,
                  'sha256': expected, 'desktop_entry': True, 'x11_startup': True}))
PY
su - piggytest -c '/usr/bin/python3 /tmp/check-release.py'
CONTAINER

# Build on Ubuntu 22.04; the result contains its own Python 3.11 and Qt runtime.
from pathlib import Path
from PyInstaller.utils.hooks import copy_metadata
import sys

root = Path(SPECPATH)
sys.path.insert(0, str(root))
from linux.paths import font_file
datas = [(str(root/'assets/macos-resources'), 'assets/macos-resources')]
for name in ('LICENSE', 'ASSET-NOTICE.md', 'README-LINUX.md', 'THIRD-PARTY-LINUX.md'):
    datas.append((str(root/name), '.'))
for package in ('numpy', 'Pillow', 'zstandard', 'PySide6-Essentials', 'shiboken6'):
    datas += copy_metadata(package)
native = []
for path in (root/'.native/usr/lib/x86_64-linux-gnu/libxcb-cursor.so.0',
             Path('/usr/lib/x86_64-linux-gnu/libxcb-cursor.so.0')):
    if path.is_file():
        native.append((str(path), '.'))
        break
for copyright in (root/'.native/usr/share/doc/libxcb-cursor0/copyright', Path('/usr/share/doc/libxcb-cursor0/copyright')):
    if copyright.is_file():
        datas.append((str(copyright), 'licenses/xcb-cursor'))
        break
for bold in (False, True):
    path = font_file(bold)
    if path is None:
        raise ValueError('构建发行包前需要 Noto Sans CJK 字体；请运行 setup-linux.sh。')
    datas.append((str(path), 'fonts'))
for path in (root/'.native/usr/share/doc/fonts-noto-cjk/copyright', Path('/usr/share/doc/fonts-noto-cjk/copyright')):
    if path.is_file():
        datas.append((str(path), 'licenses/Noto-CJK'))
        break

a = Analysis([str(root/'linux_pet.py')], pathex=[str(root)], binaries=native,
             datas=datas, hiddenimports=[],
             excludes=['tkinter', 'PySide6.QtTest', 'PySide6.QtQuick', 'PySide6.QtQml'],
             noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='googlepiggy',
          debug=False, strip=False, upx=False, console=True)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='GooglePiggy')

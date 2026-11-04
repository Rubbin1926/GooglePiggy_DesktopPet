# Qt / PySide6 / Shiboken notices

This application uses the unmodified Qt for Python 6.8.3 libraries from the official PyPI distributions.
Qt, PySide6 and Shiboken are copyright The Qt Company Ltd. and their respective contributors.
The open-source shared-library option under the GNU LGPL version 3 is used for the application runtime.
The application's own source code remains under the upstream project's MIT license.

Copies of the upstream LGPL, GPL and Qt exception texts are included in this directory.
They were obtained without modification from:

- https://github.com/pyside/pyside-setup/tree/v6.8.3/LICENSES
- https://github.com/pyside/pyside-setup/archive/refs/tags/v6.8.3.tar.gz

Qt framework source is available from the official versioned source archive:

- https://download.qt.io/archive/qt/6.8/6.8.3/single/qt-everywhere-src-6.8.3.tar.xz

The runtime is dynamically linked. Its libraries are distributed separately in `_internal/` and may be replaced with compatible modified libraries.
No Qt or Shiboken library source was modified for this port.

The adjacent `Qt-thirdparty/` directory preserves upstream license/copyright/attribution notices from the Qt 6.8.3 qtbase, qtsvg and qtimageformats source archives.
Each module's `SOURCE.json` records its exact source URL and archive SHA-256.
Ubuntu library copyright files and their referenced common license texts are collected separately under `licenses/Ubuntu/` in the portable package.

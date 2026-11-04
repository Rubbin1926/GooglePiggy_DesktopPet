# Linux 运行时与素材声明

本移植基于 Myf-ricey/GooglePiggy_DesktopPet，保留原版权、MIT License 和 ASSET-NOTICE.md。
原始角色、动画和装饰素材没有重新生成或重新授权。

Linux 发行包包含 CPython、PySide6 / Qt、Shiboken、NumPy、Pillow、zstandard，
并由 PyInstaller 打包。这些组件保留各自的许可证，并不因主项目采用 MIT 而变为 MIT。
发行包收集相应 Python distribution 的元数据和许可证；CPython 许可证另存于 `licenses/CPython/`。
Qt / PySide6 / Shiboken 6.8.3 的许可文本另存于 `licenses/Qt/`，上游第三方版权与归属声明在 `licenses/Qt-thirdparty/`；构建所用 Ubuntu 系统库的版权声明在 `licenses/Ubuntu/`。

- CPython：Python Software Foundation license；<https://www.python.org/psf/license/>。
- PySide6 / Qt / Shiboken：使用 6.8.3 的开源共享库版本；<https://doc.qt.io/qtforpython-6.8/licenses.html>。
  Qt 动态库以独立 `.so` 文件分发，源代码和许可证依照 Qt 的官方发布提供。
- NumPy、Pillow、zstandard：许可证包含在各自 `.dist-info` 中，包含其所附带的第三方声明。
- PyInstaller：<https://pyinstaller.org/en/stable/license.html>，其打包程序的分发适用 bootloader exception。
- 若附带 Ubuntu 的 `libxcb-cursor0`，相应版权及许可另存于 `licenses/xcb-cursor/`。
- 发行包的 Noto Sans CJK 字体采用 SIL Open Font License；对应声明另存于 `licenses/Noto-CJK/`。

源代码环境中的 uv 只用于安装和构建，不作为桌宠运行时加载。

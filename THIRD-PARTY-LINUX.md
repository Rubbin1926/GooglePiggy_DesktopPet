# Linux 运行时与素材声明

本移植基于 Myf-ricey/GooglePiggy_DesktopPet，保留原版权、MIT License 和 ASSET-NOTICE.md。
原始角色、动画和装饰素材没有重新生成或重新授权。

Linux 发行包包含程序源码与素材，使用 Ubuntu 自带的 CPython。
安装脚本通过 APT 安装系统依赖，并在项目虚拟环境中安装 PySide6 / Qt、Shiboken、NumPy、Pillow、zstandard。
这些组件保留各自的许可证，并不因主项目采用 MIT 而变为 MIT。
Python 依赖的元数据和许可证随各自安装包保留在 `.venv` 中；Ubuntu 包的版权声明位于系统 `/usr/share/doc/`。
Qt / PySide6 / Shiboken 6.8.3 的许可文本另存于 `licenses/Qt/`，上游第三方版权与归属声明在 `licenses/Qt-thirdparty/`。

- CPython：Python Software Foundation license；<https://www.python.org/psf/license/>。
- PySide6 / Qt / Shiboken：使用 6.8.3 的开源共享库版本；<https://doc.qt.io/qtforpython-6.8/licenses.html>。
  Qt 动态库以独立 `.so` 文件分发，源代码和许可证依照 Qt 的官方发布提供。
- NumPy、Pillow、zstandard：许可证包含在各自 `.dist-info` 中，包含其所附带的第三方声明。
- Noto Sans CJK 字体通过 Ubuntu 的 `fonts-noto-cjk` 安装，采用 SIL Open Font License；声明位于 `/usr/share/doc/fonts-noto-cjk/copyright`。

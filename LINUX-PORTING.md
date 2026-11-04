# Ubuntu 22.04 兼容基线

目标为 Ubuntu 22.04 LTS Desktop / x86_64 / GNOME Xorg，使用发行版自带的 Python 3.10。
基础安装不预设开发工具、Python 扩展包或中文字体已经存在。

## 环境约定

- 系统依赖由 `requirements-linux-apt.txt` 列出，`install-deps-linux.sh` 用 APT 补齐。
- 源码安装额外需要 `python3-venv`，虚拟环境由 `/usr/bin/python3` 创建。
- 构建额外需要 `python3-dev` 和 `binutils`；便携包从原生 `ubuntu:22.04` 容器构建。
- NumPy 等 Python 包按 Python 3.10 锁定；SHA-256 计算兼容其标准库。
- 二进制用户按照 Releases 的解压、依赖安装与启动步骤使用，无需开发环境。

## 功能范围

保留原作 21 组动画、多聊天家庭、三只子代理与 +N、拖拽贴边、权限气泡、外观、自启动和更新回滚。
共用上游状态与动画模块；Windows / macOS 的既有运行时代码保持独立。
Linux 使用四个外边缘，显示器接缝不触发隐藏。

## 最小验证

构建只执行 SHA-256 包校验、Hook 子进程及 Qt 绑定三个兼容性用例，随后检查资源并短时启动窗口。
发布验收使用全新的 `ubuntu:22.04` 容器，从公开 Releases 下载压缩包与 SHA256SUMS，按发布说明安装依赖、登记普通用户应用入口并在 X11 测试显示中短时启动。
Xvfb 仅作为测试显示服务器，不是桌面用户的安装依赖。

这不代表真实扩展屏、混合物理 DPI、Wayland 或跨日运行已完成验证。详细安装方案以 [README-LINUX.md](README-LINUX.md) 和 Releases 为准。

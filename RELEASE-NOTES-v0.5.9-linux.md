# Ubuntu 22.04 / X11 · 0.5.9 移植测试版

- 复用原作 21 组、2167 帧 RGBA 动画，提供透明置顶窗口、拖拽、躺平、休闲和四边尾巴隐藏。
- 提供多聊天家庭、三只子代理与 `+N`、独立动画进度、未读、任务跳转及完成庆祝。
- 提供权限气泡、长内容滚动、允许一次 / 拒绝、外观与实际位置预览、自启动、安装卸载以及独立 Linux 更新与回滚。

基于 Myf-ricey/GooglePiggy_DesktopPet 的 `1f69e17`，保留原版权、MIT License、素材说明和上游代码历史。
Linux 源码位于 `linux/`；原 Windows / macOS 运行时代码和动画素材保留。

独立 Python 3.11.18，固定兼容的 PySide6 / Shiboken 6.8.3。便携包包含运行时、中文字体及依赖许可，不需要改变系统 Python 或 Isaac Sim 环境。

已验证：48 项回归、14 项打包运行检查、Ubuntu 22.04 干净 CI、真实进程更新 / 回滚重启、持续绘制、用户审核后的真实 Codex 工具状态联动。
界面预览使用模拟任务；完整证据边界见 [LINUX-PORTING.md](LINUX-PORTING.md)。

尚未实测：真实扩展屏、混合物理 DPI、多种 Dock 布局与跨日使用。Wayland 原生定位暂未支持。
这是首个移植测试版，优先对齐原作功能，后续改进根据使用反馈进行。

完整解压后运行 `./start-linux.sh`；需要菜单、自启动和联动时运行 `./install-linux.sh`，再在 Codex 中审核 GooglePiggy Linux Hook。
程序目录需要保留。SHA-256 见附件 `SHA256SUMS.txt`。卸载运行 `./uninstall-linux.sh`，用户状态与备份保留。

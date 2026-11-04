# Ubuntu 移植基线与验收记录

## 范围

上游快照：`1f69e17ff28666e735ed3a9957deed00da508cbf`。
体验参照原作者介绍视频、macOS 0.5.6 和 Windows 0.5.9；先复刻原功能，不增加养成或其他产品功能。
目标环境：Ubuntu 22.04 x86_64 / GNOME/X11，专用 Python 3.11。

复用且不修改：`family_store.py`、`animation_clock.py`、`codex_observer.py`、`leisure.py`、`appearance.py`、`update_notice.py`，以及全部上游 RGBA 素材。
Linux 窗口、输入区域、安装、自启动、Hook 和更新器位于 `linux/`。

## 对照与取舍

| 功能 | Linux 对应实现 | 验证入口 |
| --- | --- | --- |
| 原作全部动作、透明边缘、动画时序 | 21 组 / 2167 帧原 RGBA；共用 manifest 与动画时钟 | `--qa-only`、Qt 启动与截图 |
| 多聊天家庭、独立进度、未读 | 共用 FamilyStore / CodexObserver | Linux Qt 测试及上游状态测试 |
| 三只子代理与 +N | 原槽位与缩放，逐 actor 状态 | 五子代理用例 |
| 拖拽、躺平 | Qt 鼠标事件、原作动作 | Qt 鼠标用例 |
| 贴边、尾巴、家庭完成后唤回 | 四外边缘；接缝排除；隐藏家庭绑定 | 负坐标、尾巴、任务事件用例 |
| 权限允许 / 拒绝 / 滚动 | Python Hook → 原子请求 → Qt 气泡 → 同请求响应 | 真实 Hook 子进程往返、超时及错配测试 |
| 外观、颜色、透明度、预览、保存 | 共用 Appearance 与原始绘制布局 | Qt 预览与冷启动缩放测试 |
| 自启动 / 安装 / 卸载 | 当前用户 desktop entry，十二项 Hook 增量合并 | 隔离 XDG 目录安装卸载测试 |
| 更新、校验、备份、回滚 | 独立 Linux Release 通道 | 包校验、恶意归档与事务回滚测试 |

平台差异：Linux 参考 Mac 的四边隐藏；尾巴露出部分沿 GNOME 工作区边缘放置，避免被面板遮挡。
Windows 0.5.9 的三边策略只保留在 Windows。Wayland 原生定位尚未支持。
源码目录通过 Git 更新；只有便携发行包使用目录替换更新。

## 已执行与待完成

- 已完成：独立 Python 3.11.18 配置；Ubuntu 22.04.5 / X11 下窗口启动与自身截图；全部素材路径校验。
- 已完成：Linux 34 项回归测试，包含真实 Hook 子进程与 Qt 权限允许往返、并发权限焦点、跨回合旧响应拒绝及 Qt 绑定引用计数；上游 14 项状态、压缩会话与内部请求过滤测试，共 48 项通过。
- 已完成：便携包构建；屏蔽开发环境路径后的独立 Python 3.11、无显示器 Hook、X11 窗口、单实例、多任务 / 子代理 / 压缩 / 中断 / 完成事件、真实新进程更新与故障回滚后重启，共 14 项运行检查通过。
- 已完成：Ubuntu 22.04 干净 CI 的测试、构建、Xvfb X11 运行与真实进程更新 / 回滚。[兼容运行时对应运行](https://github.com/Rubbin1926/GooglePiggy_DesktopPet/actions/runs/41874700206)，代码提交 `f29361c`。
- 已完成：独立临时目录中执行安装脚本；未修改宿主机默认 Python 或 Shell 配置。
- 已完成：当前用户安装、十二项 Hook 登记与用户审核；真实 Codex PreToolUse / PostToolUse 事件和工作动画已接通。程序独立后台运行，默认 Python 仍为 3.10.12，Shell / Isaac Sim 启动文件前后校验一致。
- 已完成：修复版本连续 240 秒离屏运行、5951 次绘制；实际 X11 观察模式也持续运行并接收真实 Hook 事件。
- 待现场进一步覆盖：真实 Codex 复杂多聊天 / 子代理 / 权限 / 完成组合，以及人工交互体验验收。
- 尚未实测：真实扩展屏、混合物理 DPI、多种 GNOME Dock 配置、长时间运行。

单元测试、离屏 Qt 测试、真实 X11 窗口启动和用户现场验收分别记录，不能互相代替。

## Python 3.11 绑定回归

持续运行曾在本机的 CPython 3.11.18 + PySide6 / Shiboken 6.12.0 组合下触发 `none_dealloc`。
最小例中，200 次 `QPainter.drawImage` 等 void 调用使 `None` 引用计数减少 200；同一 Python 中的 6.8.3 对照计数保持不变。
因此固定 6.8.3，并加入 `test_qt_void_bindings_do_not_consume_none_references`，再重新执行完整回归、打包运行与持续绘制验证。
此修复仅涉及桌宠自己的依赖环境。

# GooglePiggy · Ubuntu / Linux

这是 [Myf-ricey/GooglePiggy_DesktopPet](https://github.com/Myf-ricey/GooglePiggy_DesktopPet) 的 Ubuntu 移植分支。
目标是先复刻原作的动画、任务家庭、子代理和交互，再考虑新功能。
上游基线：`1f69e17ff28666e735ed3a9957deed00da508cbf`；Windows 0.5.9 / macOS 0.5.6。

**首版目标：Ubuntu 22.04 x86_64、GNOME/X11、Python 3.11。当前是移植测试版，实际验收范围见 [LINUX-PORTING.md](LINUX-PORTING.md)。**
运行时固定 PySide6 / Shiboken 6.8.3，以保留 Python 3.11 下的持续绘图稳定性。
Wayland 暂未支持原生桌宠定位；请使用登录界面中的 Ubuntu on Xorg 会话。

![Linux 界面预览；使用模拟任务展示原作动画、子代理、权限气泡和完成效果](docs/linux-preview.png)

上图使用模拟任务展示界面，不包含真实聊天内容。

## 便携包

完整解压 Linux 包到固定目录，运行 `./start-linux.sh`。包内包含专用 Python 3.11 和 Qt，无需改变系统 Python。
[下载 0.5.9 Linux 测试版](https://github.com/Rubbin1926/GooglePiggy_DesktopPet/releases/tag/v0.5.9-linux)。
需要应用菜单入口、当前用户自启动和 Codex 联动时运行：

```sh
./install-linux.sh
```

安装器会登记十二项 `GooglePiggy Linux` Hook。请在 **Codex 设置 → Hooks** 或 CLI 的 **`/hooks`** 中核对命令并信任，随后新建聊天或重启客户端。
安装器不会改写信任数据库。不要信任不认识的其他 Hook。

可使用 `./install-linux.sh --no-autostart` 或 `--no-hooks` 取消对应登记。
安装位置需要保留；移动目录后重新运行安装器，并重新审核变更的 Hook。

## 从源码运行

```sh
./setup-linux.sh
./start-linux.sh
./install-linux.sh
```

安装脚本只在项目的 `.tools/`、`.runtime/`、`.venv/`、`.uv-cache/` 和 `.native/` 下配置工具与依赖。
已有 `.venv` 必须使用 Python 3.11，脚本不会覆盖不同版本的环境。
`uv` 固定版本及下载校验值；缺失的 Python 3.11 下载到项目目录，禁止向全局 bin 安装命令。
启动脚本固定使用 `.venv/bin/python`，不需要激活环境。

Ubuntu 系统的 `/usr/bin/python3`、Shell 启动文件、Conda base、Isaac Sim 的解释器和依赖都不由安装脚本修改。
Qt 所需的 `libxcb-cursor0` 缺失时，从 Ubuntu APT 源下载并解压到 `.native/`，只由桌宠加载，不安装系统包。
中文 Noto CJK 字体缺失时也解压到项目目录；便携包附带字体和对应许可。

## 交互

- 待机呼吸，点击躺平；拖拽全家时播放拱动动画。
- 思考看书、工具执行追胡萝卜、压缩上下文整理物品，完成时跳跃与烟花；空闲时偷吃和睡觉。
- 每个聊天是一户家庭。鼠标移到大猪上显示任务列表，点击任务切换并打开 Codex 聊天。
- 子代理显示为最多三只小猪，多出的显示 `+N`；切换家庭保留各自动画进度。
- 拖到桌面外边缘隐藏，点击尾巴提前唤回。运行中的家庭隐藏后，等待其主任务成功且子代理结束再弹出庆祝，其他聊天的事件不会提前唤回。
- 权限气泡支持滚动、拒绝和允许一次；长说明需滚动至末尾才能允许。没有窗口、请求过期或详情缺失时使用 Codex 原生确认。
- 右键进入休息模式、打开外观、自启动、检查更新或退出。
- 外观设置独立调整猪猪、对话框和任务栏；预览显示在实际位置，不创建任务或发送权限决定。

Linux 使用四个外边缘，参考 macOS 行为；尾巴的可点击部分留在 GNOME 可用工作区中。
相邻显示器接缝不触发隐藏。多显示器几何测试与真实扩展屏验收分别记录。

## 状态与隐私

- 用户状态：`${XDG_STATE_HOME:-~/.local/state}/googlepiggy/`。
- 应用入口：`${XDG_DATA_HOME:-~/.local/share}/applications/googlepiggy-linux.desktop`。
- 自启动：`${XDG_CONFIG_HOME:-~/.config}/autostart/googlepiggy-linux.desktop`。
- Hook：`${CODEX_HOME:-~/.codex}/hooks.json`；变更前备份到状态目录的 `hook-backups/`，保留其他 Hook。
- 只读观察 Codex 本地元数据和生命周期记录，兼容已压缩的 `.jsonl.zst`；不修改 Codex 的数据库或聊天内容。
- 更新检查仅访问本 Fork 的 GitHub Releases；任务内容不用于更新请求。
- 异常记录：状态目录的 `pig-pet-error.log`；运行状态：`pig-heartbeat.json`。

`--state-dir PATH` 可隔离测试状态；`--no-observe` 禁用真实 Codex 观察，`--no-update-check` 禁用启动更新检查。

## 更新与卸载

便携发行包的“检查更新…”只识别本 Fork 的正式 `v版本-linux` 标签和对应 x86_64 包。
下载后检查 GitHub SHA-256 摘要、文件清单和平台，拒绝路径穿越、链接和特殊文件。
更新等待权限处理和拖动结束，保留旧目录备份；新进程启动检查失败时恢复旧目录并重新启动。
预发布包不会触发自动升级。源码运行通过 Git 更新，不直接替换源码目录。

卸载运行 `./uninstall-linux.sh`，移除本项目的应用入口、自启动及 Hook，保留用户状态和备份。
退出程序后可以手动移走便携目录；其他项目和 Isaac Sim 无需改动。

## 开发与验证

```sh
.venv/bin/python linux_pet.py --qa-only
QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest tools.test_linux_port tools.test_state_audit tools.test_compressed_rollout tools.test_internal_memory -q
.venv/bin/python -m pip install -r requirements-linux-build.txt
./build-linux.sh
```

在 Ubuntu 22.04 上构建以保持 glibc 基线。输出位于 `dist/GooglePiggy/` 与 `dist/GooglePiggy-版本-linux-x86_64.tar.gz`。
不要在正在使用的安装目录上重新构建；先构建到 `dist/`，验证后再替换或使用更新流程。

上游部分文件的已提交行尾与 `.gitattributes` 不一致；本移植不批量改写 Windows / macOS 文件。
开发时如遇到首次克隆即出现的行尾差异，可在本地 `.git/info/attributes` 添加 `* -text` 保留原始字节。

程序代码遵循原仓库 [MIT License](LICENSE)，角色与动画保留 [ASSET-NOTICE.md](ASSET-NOTICE.md)。
运行时依赖的许可证见 [THIRD-PARTY-LINUX.md](THIRD-PARTY-LINUX.md)。

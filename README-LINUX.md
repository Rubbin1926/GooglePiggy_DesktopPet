# GooglePiggy · Ubuntu / Linux

基于 [Myf-ricey/GooglePiggy_DesktopPet](https://github.com/Myf-ricey/GooglePiggy_DesktopPet)，优先保留原作动画和交互。

## 支持基线

- Ubuntu 22.04 LTS **Desktop，x86_64**。
- GNOME 的 **Ubuntu on Xorg** 会话。原生 Wayland 暂不支持；可在登录界面的齿轮菜单中选择 Xorg。
- 源码使用 Ubuntu 22.04 自带的 **Python 3.10** 创建 `.venv`，不下载其他 Python 版本。
- 便携包在原生 `ubuntu:22.04` 容器中用 Python 3.10 构建，包含运行时、Qt 和中文字体。
- Codex 联动是可选功能；未安装 Codex 时也可以使用桌宠。

![Linux 界面预览，使用模拟任务展示](docs/linux-preview.png)

## 从 Releases 安装

[下载 Linux 测试版](https://github.com/Rubbin1926/GooglePiggy_DesktopPet/releases/tag/v0.5.9-linux)，完整解压到固定目录：

```sh
mkdir -p GooglePiggy
tar -xzf GooglePiggy-0.5.9-linux-x86_64.tar.gz -C GooglePiggy
cd GooglePiggy
./install-deps-linux.sh
./start-linux.sh
```

`install-deps-linux.sh` 检查 `requirements-linux-apt.txt` 中的标准 Ubuntu 桌面库、`xdg-utils` 和中文字体，只通过 APT 安装缺少的包；普通用户需要输入 sudo 密码。
便携包本身不需要 pip 或额外的 Python 版本。

登记应用菜单入口和自启动、暂不启用 Codex 联动：

```sh
./install-linux.sh --no-hooks
```

启用 Codex 联动时，先安装 Codex，再运行 `./install-linux.sh`，在 Codex 设置 → Hooks 或 CLI `/hooks` 中审核十二项 `GooglePiggy Linux` Hook，随后新建聊天或重启客户端。
`--no-autostart` 可跳过自启动登记。程序目录需要保留；移动后重新运行安装器。

## 从源码运行

```sh
git clone https://github.com/Rubbin1926/GooglePiggy_DesktopPet.git
cd GooglePiggy_DesktopPet
./setup-linux.sh
./start-linux.sh
```

`setup-linux.sh` 自动补齐标准运行依赖以及 `python3-venv`，用 `/usr/bin/python3` 创建 Python 3.10 虚拟环境，并安装锁定的 Python 包。
启动脚本固定使用 `.venv/bin/python`，不需要手动激活。
已有非 3.10 的 `.venv` 时，先将其移走或改名再运行安装脚本。
PySide6 / Shiboken 固定为兼容版本 6.8.3。

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
退出程序后可以手动移走便携目录。

## 构建与最小检查

推荐使用干净的 Ubuntu 22.04 容器构建，构建过程仅执行三项兼容性检查、资源校验和两秒窗口启动：

```sh
docker build --target build -f Dockerfile.linux -t googlepiggy-build .
container=$(docker create googlepiggy-build)
docker cp "$container:/app/dist/." ./dist/
docker rm "$container"
```

原生 Ubuntu 22.04 上构建时，先安装 `python3-dev binutils`，运行 `./setup-linux.sh` 后，在虚拟环境内安装 `requirements-linux-build.txt`，再运行 `./build-linux.sh`。
构建脚本不自动执行完整回归。Linux CI 为手动触发。

输出为 `dist/GooglePiggy/`、Linux 压缩包和 `SHA256SUMS.txt`。不要在正在使用的程序目录上重新构建。
上游部分文件已提交的行尾与 `.gitattributes` 不一致；开发时如出现初始行尾差异，可在本地 `.git/info/attributes` 添加 `* -text`。

程序代码遵循原仓库 [MIT License](LICENSE)，角色与动画保留 [ASSET-NOTICE.md](ASSET-NOTICE.md)。依赖许可见 [THIRD-PARTY-LINUX.md](THIRD-PARTY-LINUX.md)。

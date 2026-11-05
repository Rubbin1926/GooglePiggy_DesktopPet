# Ubuntu 22.04 LTS / Python 3.10 · Linux 测试版

面向原生 **Ubuntu 22.04 LTS Desktop（x86_64）**，使用 **Ubuntu on Xorg** 会话。
源码以系统自带的 Python 3.10 为基线；本页便携包也从原生 Ubuntu 22.04 容器构建，包含 Python 3.10、Qt 和中文字体。

## 安装便携包

下载附件中的压缩包与 SHA256SUMS.txt，可先运行 `sha256sum -c SHA256SUMS.txt` 校验，再完整解压：

```sh
mkdir -p GooglePiggy
tar -xzf GooglePiggy-0.5.9-linux-x86_64.tar.gz -C GooglePiggy
cd GooglePiggy
./install-deps-linux.sh
./start-linux.sh
```

最基础的 Ubuntu 安装可能缺少 Qt 所需的 EGL / GL / XCB 库、`xdg-utils` 或中文字体。
包内的 `install-deps-linux.sh` 会检查 `requirements-linux-apt.txt`，通过 Ubuntu APT 安装缺包；普通用户需输入 sudo 密码。
便携包不需要安装 pip 或其他 Python 版本。

如提示 Wayland 定位不支持，请注销，在登录界面的齿轮菜单选择 **Ubuntu on Xorg** 后登录。

## 菜单、自启动与 Codex

- 仅使用桌宠：运行 `./install-linux.sh --no-hooks` 登记应用菜单和自启动。
- 使用 Codex 联动：先安装 Codex，再运行 `./install-linux.sh`，在 Codex 设置 → Hooks 或 CLI `/hooks` 中审核 GooglePiggy Linux。
- `--no-autostart` 可跳过自启动登记；程序目录需要保留。
- 卸载运行 `./uninstall-linux.sh`，用户状态和备份保留。

## 审批方式可选

**审批先遵循 Codex 的权限规则，桌宠设置只决定人工审批出现在哪里。**

- **帮我批准**：直接交给 Codex 自动审查，无论小猪选择哪种审批方式，都不额外弹出人工审批。
- **完全访问权限、已经允许的操作**：小猪不弹审批。
- **请求审批**：按桌宠设置显示小猪或 Codex 原生审批。
- **配置文件模式**：遵循 Codex 合并 `.toml` 与会话设置后的权限；要求用户确认时，才进入桌宠选择的审批方式。

右键小猪 → **审批方式**，默认“小猪人工审批”，支持允许一次或拒绝。
也可切换为“Codex 原生审批，小猪提示跳转”，在 Codex 完成人工确认。
设置会保存；请先处理当前审批，再切换后续请求的模式。
无法确认当前轮次权限时使用 Codex 原生流程；Codex 的拒绝结果不会被小猪改成允许。

## 模式与任务显示修复

- 修复压缩上下文后的会话恢复丢失完成类型、后续审批使真正结束事件被丢弃的问题，避免任务结束后仍卡在问号和休息禁用状态。
- 已结束轮次的迟发审批不会重新激活任务，也不会覆盖已结束或更新轮次的 Hook 状态。
- 右键菜单勾选当前模式；已启用的“状态互动（Codex）”不再显示为可重复执行的按钮。
- 休息菜单与动画使用相同的阻塞判断；运行任务、等待审批、暂停、庆祝或其他动作未结束时，显示具体原因，避免“可点击却没有动作”。
- 悬停任务列表显示“实时状态 · 聊天标题”。标题对应 Codex 聊天名称，同一聊天继续提问时仍保留；思考、执行、审批、暂停和完成状态会更新。
- 手动休息约 6.4 秒后进入循环睡眠，新任务自动唤醒。普通待机主要是轻微呼吸，自动入睡约需 3–30 分钟。

模式菜单、休息条件、睡眠与唤醒、任务文字、压缩后的结束事件和过期审批的九项针对性检查已通过。完整功能表见 README。

## 从源码安装

先下载本页的 Source code（zip）并解压，再运行 `./setup-linux.sh`；也可先安装 Git 拉取仓库。
脚本补齐标准桌面依赖及 `python3-venv`，使用 `/usr/bin/python3` 创建 Python 3.10 虚拟环境并安装锁定的包。
构建便携包另需 `python3-dev binutils`，或使用仓库的 `Dockerfile.linux`。

保留原作动画、多任务、子代理、拖拽贴边、权限气泡、外观与更新回滚。
代码与素材归属保留原仓库声明，依赖许可随包附带。
完整说明见 [README-LINUX.md](README-LINUX.md)。

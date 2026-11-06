支持 **Ubuntu 22.04 / 24.04 LTS Desktop、x86_64、GNOME Xorg**。
使用各系统自带的 Python：22.04 为 **3.10**，24.04 为 **3.12**；依赖安装到项目 `.venv`，安装包不携带额外解释器。

**需要 Xorg 会话。** 桌面终端运行 `echo "$XDG_SESSION_TYPE"` 应输出 `x11`；若为 `wayland`，请注销，在登录齿轮菜单选择 **Ubuntu on Xorg**。Wayland 暂不支持。

## 安装

下载附件中的压缩包与 `SHA256SUMS.txt`，在下载目录执行：

```sh
sha256sum -c SHA256SUMS.txt
mkdir -p GooglePiggy
tar -xzf GooglePiggy-0.5.9-linux-x86_64.tar.gz -C GooglePiggy
cd GooglePiggy
./setup-linux.sh
./start-linux.sh
```

首次安装需要联网和 sudo 密码：脚本通过 Ubuntu APT 补齐桌面库、中文字体及 `python3-venv`，再从 PyPI 安装项目依赖。不更改系统 Python，也不向 24.04 安装 Python 3.10。

## 菜单、自启动与 Codex

- `./install-linux.sh --no-hooks`：登记应用菜单和自启动。
- `./install-linux.sh`：先安装 Codex，再登记联动；在 Codex 设置 → Hooks 或 CLI `/hooks` 中审核十二项 GooglePiggy Linux。
- `--no-autostart`：跳过自启动登记。移动程序目录后需重新登记。
- `./uninstall-linux.sh`：移除本项目入口、自启动和 Hook，保留用户状态与备份。

## 使用要点

- **小猪习性…**：默认全部任务结束后空闲 5 秒开睡，手动唤醒后清醒 15 秒；可调 1–3600 秒。
  点 **保存** 才生效，并显示成功确认；未保存关闭不提交，“恢复默认”后也需保存。
- **审批方式**只决定人工审批出现在哪里：小猪允许/拒绝，或 Codex 原生审批加跳转提示。
  “帮我批准”和完全访问权限不额外弹小猪审批；`.toml` 遵循 Codex 最终规则，需要人工时按上述方式分流，拒绝结果保留。
- **任务列表**：悬停显示实时任务状态，采用连续柔粉渐变；多任务以细标记和字重区分当前项。
- **外观…**：对话框和任务框可分别一键恢复小猪色，保留各自的大小和间距。
- **拖到四边隐藏**，点击完整尾巴或周围区域唤回；位置适配实际工作区、Dock 和面板。
- 保留多聊天、子代理、拖拽、压缩上下文动画、完成提醒和外观设置。

## 更新、源码与许可

系统 Python 版通过 Releases 或 Git 手动更新；测试版不触发自动升级。更新前退出桌宠并备份旧目录，新目录运行 `./setup-linux.sh` 和 `./install-linux.sh`，用户状态保留。
源码使用同一安装步骤；`./build-linux.sh` 可重新打包，无需额外解释器。

代码遵循原仓库 MIT License，素材和依赖许可随包说明。
详细安装、依赖与验收范围见 [README-LINUX.md](README-LINUX.md)。

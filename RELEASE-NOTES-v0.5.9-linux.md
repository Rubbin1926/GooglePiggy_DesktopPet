支持 **Ubuntu 22.04 Desktop、x86_64、Ubuntu on Xorg**。便携包包含 Python 3.10、Qt 和中文字体。

## 安装

下载附件中的压缩包与 `SHA256SUMS.txt`，在下载目录执行：

```sh
sha256sum -c SHA256SUMS.txt
mkdir -p GooglePiggy
tar -xzf GooglePiggy-0.5.9-linux-x86_64.tar.gz -C GooglePiggy
cd GooglePiggy
./install-deps-linux.sh
./start-linux.sh
```

依赖脚本通过 Ubuntu APT 补齐缺少的桌面库和工具，需要 sudo 密码；便携包无需 pip 或另装 Python。
使用 Wayland 时，请注销并在登录齿轮菜单选择 **Ubuntu on Xorg**。
精简桌面若缺少 GNOME Dock 设置读取工具，可安装 `libglib2.0-bin`；不可用时仍按系统工作区放置尾巴。

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
- **任务列表**：悬停显示实时任务状态，粉色气泡与字体风格和更新提示保持一致。
- **外观…**：对话框和任务框可分别一键恢复小猪色，保留各自的大小和间距。
- **拖到四边隐藏**，点击完整尾巴或周围区域唤回；位置适配实际工作区、Dock 和面板。
- 保留多聊天、子代理、拖拽、压缩上下文动画、完成提醒和外观设置。

## 更新、源码与许可

此为测试版，不参与自动升级；更新前退出桌宠，完整替换程序目录。用户状态保存在用户目录中。
源码解压后运行 `./setup-linux.sh`；构建另需 `python3-dev binutils`，也可使用仓库的 `Dockerfile.linux`。

代码遵循原仓库 MIT License，素材和依赖许可随包附带。
详细安装、依赖与功能说明见 [README-LINUX.md](README-LINUX.md)。

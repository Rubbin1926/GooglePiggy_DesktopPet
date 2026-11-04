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

## 从源码安装

运行 `./setup-linux.sh`：脚本补齐标准桌面依赖及 `python3-venv`，使用 `/usr/bin/python3` 创建 Python 3.10 虚拟环境并安装锁定的包。
构建便携包另需 `python3-dev binutils`，或使用仓库的 `Dockerfile.linux`。

保留原作动画、多任务、子代理、拖拽贴边、权限气泡、外观与更新回滚。
代码与素材归属保留原仓库声明，依赖许可随包附带。
完整说明见 [README-LINUX.md](README-LINUX.md)。

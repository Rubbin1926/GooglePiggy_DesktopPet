"""User-level launchers and additive Hook registration, with reversible backups."""
import fcntl
import json
import shlex
import shutil
import sys
import time
import uuid
from pathlib import Path

from codex_bridge import atomic_json
from linux.hook import EVENTS
from linux.paths import app_root, codex_home, config_dir, data_dir, resource_root, state_dir

MARKER = 'GooglePiggy Linux'
DESKTOP_NAME = 'googlepiggy-linux.desktop'
DESKTOP_MARKER = 'X-GooglePiggy-Linux=true'
ICON_NAME = 'AppIcon-1024.png'


def command(root=None, interpreter=None):
    root = Path(root or app_root())
    if getattr(sys, 'frozen', False) or (root/'googlepiggy').is_file():
        return [str(root/'googlepiggy')]
    return [str(Path(interpreter or sys.executable).absolute()), str(root/'linux_pet.py')]


def _launcher_path():
    return data_dir()/'applications'/DESKTOP_NAME


def _icon_path():
    return data_dir()/'googlepiggy'/ICON_NAME


def _replace_file(path, contents):
    temp = path.with_name(f'.{path.name}.{uuid.uuid4().hex}.tmp')
    try:
        temp.write_bytes(contents)
        if path.exists():
            temp.chmod(path.stat().st_mode & 0o777)
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)


def _install_icon():
    icon = _icon_path()
    contents = (resource_root()/ICON_NAME).read_bytes()
    if not icon.is_file() or icon.read_bytes() != contents:
        icon.parent.mkdir(parents=True, exist_ok=True)
        _replace_file(icon, contents)


def desktop_text(args):
    def quote(value):
        value = value.replace('%', '%%')
        for char in ('\\', '"', '`', '$'):
            value = value.replace(char, '\\'+char)
        return '"'+value+'"'
    return ('[Desktop Entry]\nType=Application\nName=GooglePiggy 小猪桌宠\n'
            'Comment=Codex desktop companion for Ubuntu\n'
            'Exec='+' '.join(quote(arg) for arg in args)+'\n'
            f'Icon={_icon_path()}\nTerminal=false\nCategories=Utility;\n'
            f'StartupNotify=false\n{DESKTOP_MARKER}\n')


def autostart_path():
    return config_dir()/'autostart'/DESKTOP_NAME


def repair_registered_icons():
    """Migrate icon references from older package layouts on GUI startup."""
    root = app_root()
    legacy_icons = {root/'assets/macos-resources'/ICON_NAME,
                    root/'_internal/assets/macos-resources'/ICON_NAME,
                    resource_root()/ICON_NAME}
    legacy_lines = {f'Icon={icon}'.encode() for icon in legacy_icons}
    icon = _icon_path()
    icon_line = f'Icon={icon}'.encode()
    for entry in (_launcher_path(), autostart_path()):
        if entry.is_symlink():
            continue
        try:
            contents = entry.read_bytes()
            if DESKTOP_MARKER.encode() not in contents.splitlines():
                continue
            lines = contents.splitlines(keepends=True)
            for index, line in enumerate(lines):
                if not line.startswith(b'Icon='):
                    continue
                old = line.rstrip(b'\r\n')
                if old in legacy_lines:
                    _install_icon()
                    lines[index] = icon_line + line[len(old):]
                    if entry.read_bytes() == contents:
                        _replace_file(entry, b''.join(lines))
                elif old == icon_line and not icon.is_file():
                    _install_icon()
                break
        except OSError:
            # A missing or unwritable launcher must not prevent the pet from starting.
            continue


def autostart_enabled():
    path = autostart_path()
    return path.is_file() and 'Hidden=true' not in path.read_text(encoding='utf-8')


def set_autostart(enabled, args=None):
    path = autostart_path()
    if enabled:
        _install_icon()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(desktop_text(args or command())+'X-GNOME-Autostart-enabled=true\n', encoding='utf-8')
        if not autostart_enabled():
            raise OSError('无法读回自启动配置')
    elif path.exists():
        if DESKTOP_MARKER not in path.read_text(encoding='utf-8'):
            raise ValueError('自启动文件不是本项目创建的，已保留')
        path.unlink()


def ours(handler):
    return (isinstance(handler, dict) and handler.get('statusMessage') == MARKER and
            '--hook' in handler.get('command', ''))


def merge_hooks(value, hook_command=None):
    """Remove only our exact marker; retain unrelated events, groups and handlers."""
    value = json.loads(json.dumps(value))
    if not isinstance(value, dict) or not isinstance(value.get('hooks', {}), dict):
        raise ValueError('现有 hooks.json 格式无效，未覆盖')
    hooks = value.setdefault('hooks', {})
    for event, groups in list(hooks.items()):
        if not isinstance(groups, list):
            raise ValueError('现有 Hook 事件格式无效，未覆盖')
        retained = []
        for group in groups:
            if not isinstance(group, dict) or not isinstance(group.get('hooks'), list):
                raise ValueError('现有 Hook 分组格式无效，未覆盖')
            group['hooks'] = [h for h in group['hooks'] if not ours(h)]
            if group['hooks']:
                retained.append(group)
        if retained:
            hooks[event] = retained
        else:
            del hooks[event]
    if hook_command:
        for event in EVENTS:
            timeout = 600 if event == 'PermissionRequest' else 3 if event == 'Interrupt' else 10
            hooks.setdefault(event, []).append({'hooks': [{'type': 'command', 'command': hook_command,
                                                  'timeout': timeout, 'statusMessage': MARKER}]})
    return value


def register_hooks(hook_command=None):
    home = codex_home()
    home.mkdir(parents=True, exist_ok=True)
    path = home/'hooks.json'
    # Coordinate two installer invocations without changing Codex's trust store.
    with (home/'.googlepiggy-install.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        value = json.loads(path.read_text(encoding='utf-8-sig')) if path.exists() else {}
        merged = merge_hooks(value, hook_command)
        if merged == value:
            return
        if path.exists():
            backups = state_dir()/'hook-backups'
            backups.mkdir(parents=True, exist_ok=True, mode=0o700)
            backup = backups/f'hooks-{time.strftime("%Y%m%d-%H%M%S")}-{uuid.uuid4().hex[:8]}.json'
            shutil.copy2(path, backup)
        atomic_json(path, merged)


def install(enable_autostart=True, hooks=True):
    args = command()
    state_dir().mkdir(parents=True, exist_ok=True, mode=0o700)
    if hooks:
        register_hooks(shlex.join(args+['--hook']))
    _install_icon()
    launcher = _launcher_path()
    launcher.parent.mkdir(parents=True, exist_ok=True)
    launcher.write_text(desktop_text(args), encoding='utf-8')
    if enable_autostart:
        set_autostart(True, args)
    atomic_json(state_dir()/'installation.json', {'root': str(app_root()), 'command': args})
    print('已创建应用入口'+('与自启动。' if enable_autostart else '。'))
    if hooks:
        print('已登记十二项 Hook。请在 Codex 设置 → Hooks，或 CLI /hooks 中检查并信任 GooglePiggy Linux。')


def uninstall():
    register_hooks()
    set_autostart(False)
    path = _launcher_path()
    if path.exists() and DESKTOP_MARKER in path.read_text(encoding='utf-8'):
        path.unlink()
    _icon_path().unlink(missing_ok=True)
    print('已移除本项目的应用入口、自启动和 Hook；用户状态、备份和其他 Hook 均保留。')

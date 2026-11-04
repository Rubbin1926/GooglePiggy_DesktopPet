"""Linux paths; never change the caller's Python or shell environment."""
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


def app_root():
    return Path(sys.executable).resolve().parent if getattr(sys, 'frozen', False) else Path(__file__).resolve().parents[1]


def resource_root():
    return Path(getattr(sys, '_MEIPASS', app_root())) / 'assets' / 'macos-resources'


def state_dir():
    override = os.environ.get('GOOGLEPIGGY_STATE_DIR')
    if override:
        return Path(override).expanduser()
    return Path(os.environ.get('XDG_STATE_HOME', str(Path.home() / '.local/state'))) / 'googlepiggy'


def config_dir():
    return Path(os.environ.get('XDG_CONFIG_HOME', str(Path.home() / '.config')))


def data_dir():
    return Path(os.environ.get('XDG_DATA_HOME', str(Path.home() / '.local/share')))


def codex_home():
    return Path(os.environ.get('CODEX_HOME', str(Path.home() / '.codex')))


def font_file(bold=False):
    name = 'NotoSansCJK-'+('Bold' if bold else 'Regular')+'.ttc'
    roots = [Path(getattr(sys, '_MEIPASS', app_root()))/'fonts',
             app_root()/'.native/usr/share/fonts/opentype/noto',
             Path('/usr/share/fonts/opentype/noto')]
    return next((root/name for root in roots if (root/name).is_file()), None)


def read_json(path):
    try:
        value = Path(path).read_text(encoding='utf-8-sig')
        return json.loads(value)
    except (OSError, ValueError):
        return None


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def pid_alive(pid):
    try:
        pid = int(pid)
        if pid <= 0:
            return False
        os.kill(pid, 0)
        return True
    except PermissionError:
        return True
    except (OSError, TypeError, ValueError):
        return False

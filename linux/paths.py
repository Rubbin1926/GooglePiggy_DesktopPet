"""Linux paths; never change the caller's Python or shell environment."""
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

HABIT_DEFAULTS = {'idleSleepSeconds': 5, 'wakeAwakeSeconds': 15}
HABIT_LIMITS = (1, 3600)


def app_root():
    return Path(sys.executable).resolve().parent if getattr(sys, 'frozen', False) else Path(__file__).resolve().parents[1]


def resource_root():
    return Path(getattr(sys, '_MEIPASS', app_root())) / 'assets' / 'macos-resources'


def state_dir():
    override = os.environ.get('GOOGLEPIGGY_STATE_DIR')
    if override:
        return Path(override).expanduser()
    return Path(os.environ.get('XDG_STATE_HOME') or Path.home() / '.local/state') / 'googlepiggy'


def config_dir():
    return Path(os.environ.get('XDG_CONFIG_HOME') or Path.home() / '.config')


def data_dir():
    return Path(os.environ.get('XDG_DATA_HOME') or Path.home() / '.local/share')


def codex_home():
    return Path(os.environ.get('CODEX_HOME') or Path.home() / '.codex')


def font_file(bold=False):
    name = 'NotoSansCJK-'+('Bold' if bold else 'Regular')+'.ttc'
    roots = [Path(getattr(sys, '_MEIPASS', app_root()))/'fonts',
             Path('/usr/share/fonts/opentype/noto')]
    return next((root/name for root in roots if (root/name).is_file()), None)


def read_json(path):
    try:
        value = Path(path).read_text(encoding='utf-8-sig')
        return json.loads(value)
    except (OSError, ValueError):
        return None


def approval_mode(directory=None):
    value = read_json(Path(directory or state_dir())/'settings.json')
    return 'codex' if isinstance(value, dict) and value.get('approvalMode') == 'codex' else 'pet'


def habits_settings(directory=None):
    values = read_json(Path(directory or state_dir())/'settings.json')
    values = values if isinstance(values, dict) else {}
    return {key: min(HABIT_LIMITS[1], max(HABIT_LIMITS[0], values[key]))
            if type(values.get(key)) is int else default for key, default in HABIT_DEFAULTS.items()}


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

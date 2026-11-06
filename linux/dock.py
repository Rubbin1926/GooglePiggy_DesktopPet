"""Optional, read-only GNOME Dock preferences; never block the GUI on dconf."""
import os
import subprocess
import sys
import threading


class DockSettings:
    def __init__(self):
        self.value, self.checked_at, self.reading = None, float('-inf'), False

    def poll(self, now):
        if not self.reading and now-self.checked_at >= 2:
            self.checked_at, self.reading = now, True
            threading.Thread(target=self._read, daemon=True).start()
        return self.value

    def _read(self):
        try:
            env = dict(os.environ)
            if getattr(sys, 'frozen', False):
                original = env.pop('LD_LIBRARY_PATH_ORIG', None)
                if original is None:
                    env.pop('LD_LIBRARY_PATH', None)
                else:
                    env['LD_LIBRARY_PATH'] = original
            result = subprocess.run(['/usr/bin/gsettings', 'list-recursively',
                'org.gnome.shell.extensions.dash-to-dock'], env=env,
                capture_output=True, text=True, timeout=1)
            values = {}
            for line in result.stdout.splitlines():
                parts = line.split(None, 2)
                if len(parts) == 3 and parts[1] in {'dock-position','dash-max-icon-size','multi-monitor','dock-fixed'}:
                    values[parts[1]] = parts[2]
            edge = values['dock-position'].strip("'\"").lower()
            size = int(values['dash-max-icon-size'])
            if (result.returncode or edge not in {'left','right','top','bottom'} or size <= 0 or
                any(values[key] not in {'true','false'} for key in ('multi-monitor','dock-fixed'))):
                raise ValueError('Unavailable Dock preferences')
            self.value = edge, size+32, values['multi-monitor'] == 'true', values['dock-fixed'] == 'true'
        except (OSError, ValueError, KeyError, subprocess.TimeoutExpired):
            self.value = None
        finally:
            self.reading = False

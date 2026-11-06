"""Exercise an installed system-Python package using isolated task events."""
import argparse
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from codex_bridge import atomic_json, publish_event
from linux import VERSION
from linux.paths import read_json


def wait_for(predicate, timeout=15):
    deadline = time.monotonic()+timeout
    while time.monotonic() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(.1)
    raise AssertionError('Timed out waiting for packaged runtime')


def stop(process):
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


def stop_heartbeat_process(state, executable):
    heartbeat = read_json(state/'pig-heartbeat.json') or {}
    pid = heartbeat.get('pid')
    if isinstance(pid, int):
        proc = Path(f'/proc/{pid}/exe')
        try:
            if str(executable.parent/'linux_pet.py') in Path(f'/proc/{pid}/cmdline').read_bytes().decode().split('\0'):
                os.kill(pid, signal.SIGTERM)
                wait_for(lambda: not proc.exists(), timeout=6)
        except ProcessLookupError:
            pass


def run(executable, report, platform):
    checks = {}
    report.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='googlepiggy-runtime-') as tmp:
        root = Path(tmp)
        env = dict(os.environ, QT_QPA_PLATFORM=platform, CODEX_HOME=str(root/'empty-codex'),
                   PYTHONHOME='/nonexistent-piggy-test-home', PYTHONPATH='/nonexistent-piggy-test-path', PATH='/usr/bin:/bin')
        # This deliberately excludes the development venv.
        qa = subprocess.run([str(executable), '--qa-only'], env=env, capture_output=True, text=True, timeout=15, check=True)
        info = json.loads(qa.stdout)
        checks['animation_assets'] = info['frames'] == 2167 and info['animations'] == 21
        checks['system_python'] = not info.get('frozen') and info['python'].split('.')[:2] == [str(v) for v in sys.version_info[:2]]
        hook_env = dict(env)
        hook_env.pop('DISPLAY', None)
        hook_env.pop('WAYLAND_DISPLAY', None)
        hook_state = root/'headless-hook'
        hook = subprocess.run([str(executable), '--hook', '--state-dir', str(hook_state)],
                              input=json.dumps({'hook_event_name': 'SessionStart', 'session_id': 'headless'}),
                              env=hook_env, capture_output=True, text=True, timeout=10, check=True)
        checks['hook_without_display'] = json.loads(hook.stdout) == {} and len(list((hook_state/'family-events').glob('*.json'))) == 1
        state = root/'state'
        screenshot = report.parent/'linux-packaged-x11.png'
        with (report.parent/'runtime.log').open('w') as log:
            process = subprocess.Popen([str(executable), '--state-dir', str(state), '--no-observe',
                      '--no-update-check', '--quit-after', '90', '--capture', str(screenshot)], env=env, stdout=log, stderr=log)
            try:
                def heartbeat():
                    return read_json(state/'pig-heartbeat.json') or {}
                first = wait_for(lambda: (h if (h := heartbeat()).get('window_visible') else None))
                checks['native_window'] = first['platform'] == platform
                duplicate = subprocess.run([str(executable), '--state-dir', str(state), '--no-observe', '--no-update-check'],
                                           env=env, capture_output=True, text=True, timeout=10, check=True)
                checks['single_instance'] = '已在运行' in duplicate.stdout and heartbeat()['pid'] == process.pid
                def event(name, session='runtime-A', agent=''):
                    publish_event(state, {'event': name, 'session_id': session, 'turn_id': 'test-turn', 'agent_id': agent})
                event('UserPromptSubmit')
                wait_for(lambda: heartbeat().get('current_key') == 'reading')
                event('PreToolUse')
                wait_for(lambda: heartbeat().get('current_key') == 'carrot')
                checks['thinking_and_tools'] = True
                for i in range(5):
                    event('SubagentStart', agent='runtime-child-'+str(i))
                wait_for(lambda: len(heartbeat().get('families', [])) == 6)
                event('UserPromptSubmit', 'runtime-B')
                wait_for(lambda: heartbeat().get('selected_family') == 'runtime-B')
                for i in range(5):
                    event('SubagentStop', agent='runtime-child-'+str(i))
                event('Stop', 'runtime-B')
                wait_for(lambda: any(n['id'] == 'runtime-A' and n['status'] == 'working' for n in heartbeat().get('families', [])))
                checks['multitask_and_children'] = True
                event('PreCompact')
                wait_for(lambda: heartbeat().get('current_key', '').startswith('packing_'))
                event('PostCompact')
                event('PreToolUse')
                wait_for(lambda: heartbeat().get('current_key') == 'carrot')
                checks['compaction_resume'] = True
                event('Interrupt')
                wait_for(lambda: heartbeat().get('current_key') == 'question')
                event('UserPromptSubmit')
                wait_for(lambda: heartbeat().get('current_key') == 'reading')
                event('Stop')
                wait_for(lambda: heartbeat().get('current_key') == 'jump')
                checks['interrupt_resume_and_completion'] = True
                checks['own_window_capture'] = screenshot.is_file()
            finally:
                stop(process)
        print('Packaged lifecycle and single-instance checks passed.', flush=True)
        # Follow the documented manual-update path in a new directory and keep
        # state outside the installation. No real desktop entries or hooks change.
        installed = root/'updated-app'
        shutil.copytree(executable.parent, installed,
                        ignore=shutil.ignore_patterns('.venv', '__pycache__'))
        settings = {'approvalMode': 'codex', 'idleSleepSeconds': 7, 'wakeAwakeSeconds': 17}
        appearance = {'petScale': 1.25, 'taskOpacity': .8, 'taskColor': '#ffe4ed'}
        atomic_json(state/'settings.json', settings)
        atomic_json(state/'appearance.json', appearance)
        env.update(XDG_DATA_HOME=str(root/'data'), XDG_CONFIG_HOME=str(root/'config'),
                   XDG_STATE_HOME=str(root/'xdg-state'), GOOGLEPIGGY_STATE_DIR=str(state))
        with (report.parent/'reinstall.log').open('w') as log:
            subprocess.run([str(installed/'setup-linux.sh')], env=env, stdout=log, stderr=log,
                           timeout=180, check=True)
            subprocess.run([str(installed/'googlepiggy'), '--install', '--no-autostart'],
                           env=env, stdout=log, stderr=log, timeout=15, check=True)
            launcher = root/'data/applications/googlepiggy-linux.desktop'
            subprocess.run(['desktop-file-validate', str(launcher)], env=env, check=True)
            checks['registered_launcher_and_hooks'] = launcher.is_file() and (root/'empty-codex/hooks.json').is_file()
            try:
                subprocess.run(['gio', 'launch', str(launcher)], env=env, stdout=log,
                               stderr=log, timeout=15, check=True)
                restored = wait_for(lambda: (h if (h := read_json(state/'pig-heartbeat.json') or {}).get('window_visible')
                                             and h.get('pid') != process.pid else None))
                checks['launch_from_desktop_entry'] = restored['platform'] == platform
                checks['settings_after_reinstall'] = (restored['approval_mode'] == 'codex'
                    and restored['habits'] == {'idleSleepSeconds': 7, 'wakeAwakeSeconds': 17}
                    and all(restored['appearance'][key] == value for key, value in appearance.items()))
            finally:
                stop_heartbeat_process(state, installed/'googlepiggy')
            subprocess.run([str(installed/'googlepiggy'), '--uninstall'], env=env,
                           stdout=log, stderr=log, timeout=15, check=True)
            checks['uninstall_keeps_settings'] = not launcher.exists() and read_json(state/'settings.json') == settings
        print('Manual reinstall, desktop launch, settings and uninstall passed.', flush=True)
    result = {'passed': all(checks.values()), 'platform': platform, 'version': VERSION+'-linux', 'checks': checks}
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result))
    if not result['passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--exe', type=Path, required=True)
    parser.add_argument('--report', type=Path, default=Path('qa/linux-runtime.json'))
    parser.add_argument('--platform', choices=('xcb', 'offscreen'), default='xcb')
    args = parser.parse_args()
    run(args.exe.resolve(), args.report.resolve(), args.platform)

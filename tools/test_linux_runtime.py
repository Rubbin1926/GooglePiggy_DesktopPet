"""Exercise the packaged executable on X11 using isolated, synthetic task events."""
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
from linux.update import MANIFEST, digest


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
            if proc.resolve() == executable.resolve():
                os.kill(pid, signal.SIGTERM)
                wait_for(lambda: not proc.exists(), timeout=6)
        except ProcessLookupError:
            pass


def run(executable, report, platform):
    checks = {}
    with tempfile.TemporaryDirectory(prefix='googlepiggy-runtime-') as tmp:
        root = Path(tmp)
        env = dict(os.environ, QT_QPA_PLATFORM=platform, CODEX_HOME=str(root/'empty-codex'),
                   PYTHONHOME='/nonexistent-piggy-test-home', PYTHONPATH='/nonexistent-piggy-test-path', PATH='/usr/bin:/bin')
        # This deliberately excludes the development venv and system Python 3.11.
        qa = subprocess.run([str(executable), '--qa-only'], env=env, capture_output=True, text=True, timeout=15, check=True)
        info = json.loads(qa.stdout)
        checks['bundled_python_and_assets'] = info['frames'] == 2167
        state = root/'state'
        screenshot = report.parent/'linux-packaged-x11.png'
        with (root/'runtime.log').open('w') as log:
            process = subprocess.Popen([str(executable), '--state-dir', str(state), '--no-observe',
                      '--no-update-check', '--quit-after', '40', '--capture', str(screenshot)], env=env, stdout=log, stderr=log)
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
        # Test replacement and real-process rollback without touching the installed app.
        print('Packaged lifecycle and single-instance checks passed.', flush=True)
        source = executable.parent
        for healthy in (False, True):
            installed = root/('installed-ok' if healthy else 'installed-rollback')
            shutil.copytree(source, installed)
            candidate = source
            if not healthy:
                candidate = root/'broken-candidate'
                candidate.mkdir()
                (candidate/'googlepiggy').write_text('#!/bin/sh\nexit 7\n')
                (candidate/'googlepiggy').chmod(0o755)
                atomic_json(candidate/MANIFEST, {'schema': 1, 'platform': 'linux-x86_64', 'version': VERSION,
                            'files': {'googlepiggy': digest(candidate/'googlepiggy')}})
            update_state = root/('update-ok' if healthy else 'update-rollback')
            update_state.mkdir()
            job = update_state/'job.json'
            atomic_json(job, {'target': str(installed), 'package': str(candidate), 'version': VERSION,
                              'old_pid': 99999999, 'state_dir': str(update_state)})
            try:
                helper_log = update_state/'helper.log'
                # A restarted GUI inherits stdout. A file avoids waiting for the
                # long-lived GUI to close the update helper's captured pipe.
                with helper_log.open('w') as log:
                    subprocess.run([str(installed/'googlepiggy'), '--apply-update', str(job)],
                                   env=env, stdout=log, stderr=log, timeout=35)
                outcome = read_json(update_state/'last-update.json')
                if outcome is None:
                    raise AssertionError(helper_log.read_text()[-3000:])
                checks['real_update' if healthy else 'real_rollback'] = outcome['ok'] is healthy
                wait_for(lambda: (read_json(update_state/'pig-heartbeat.json') or {}).get('window_visible'))
                checks['relaunch_after_update' if healthy else 'relaunch_after_rollback'] = True
                print('Real update passed.' if healthy else 'Real rollback passed.', flush=True)
            finally:
                stop_heartbeat_process(update_state, installed/'googlepiggy')
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

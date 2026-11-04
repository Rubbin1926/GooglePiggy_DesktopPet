"""Recoverable folder replacement. Imported completely before moving the old app."""
import json
import os
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path

from codex_bridge import atomic_json
from linux.paths import pid_alive, read_json
from linux.update import validate_tree


def install_transaction(target, package, expected, launch, healthy, stop):
    target, package = Path(target), Path(package)
    validate_tree(package, expected)
    if (target/'.git').exists():
        raise ValueError('源码目录请使用 Git 更新；自动替换仅用于发行包')
    suffix = time.strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:8]
    stage = target.with_name('.googlepiggy-stage-'+suffix)
    backup = target.with_name(target.name+'.backup-'+suffix)
    child, moved_old = None, False
    try:
        shutil.copytree(package, stage, symlinks=False)
        validate_tree(stage, expected)
        os.replace(target, backup)
        moved_old = True
        os.replace(stage, target)
        child = launch(target)
        if not healthy(child, expected):
            raise RuntimeError('新版未通过启动检查')
        return backup
    except Exception:
        if child is not None:
            stop(child)
        if moved_old:
            if target.exists():
                os.replace(target, target.with_name(target.name+'.failed-'+suffix))
            os.replace(backup, target)
            launch(target)
        raise
    finally:
        if stage.exists():
            shutil.rmtree(stage)


def apply_job(path):
    job = json.loads(Path(path).read_text(encoding='utf-8'))
    target, package = Path(job['target']).resolve(), Path(job['package']).resolve()
    if target != Path(sys.executable).resolve().parent or not getattr(sys, 'frozen', False):
        raise ValueError('更新助手只允许替换自己的发行包目录')
    if not (target/'googlepiggy').is_file():
        raise ValueError('当前发行包缺少程序')
    deadline = time.monotonic()+15
    while pid_alive(job['old_pid']) and time.monotonic() < deadline:
        time.sleep(.1)
    if pid_alive(job['old_pid']):
        raise RuntimeError('旧版未退出，已保留原安装')
    directory = Path(job['state_dir'])
    def launch(root):
        return subprocess.Popen([str(root/'googlepiggy'), '--state-dir', str(directory), '--no-update-check'], cwd=root)
    def healthy(child, expected):
        for _ in range(100):
            if child.poll() is not None:
                return False
            heartbeat = read_json(directory/'pig-heartbeat.json') or {}
            if heartbeat.get('pid') == child.pid and heartbeat.get('version') == expected+'-linux' and heartbeat.get('window_visible'):
                return True
            time.sleep(.1)
        return False
    def stop(child):
        if child.poll() is None:
            child.terminate()
            try:
                child.wait(timeout=3)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()
    try:
        backup = install_transaction(target, package, job['version'], launch, healthy, stop)
        atomic_json(directory/'last-update.json', {'ok': True, 'backup': str(backup), 'version': job['version']})
    except Exception as error:
        atomic_json(directory/'last-update.json', {'ok': False, 'error': str(error)})
        raise

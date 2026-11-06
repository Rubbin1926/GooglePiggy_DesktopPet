#!/usr/bin/env python3
"""Linux entry point. Hooks and installers do not load the Qt runtime."""
import argparse
import json
import os
import sys
from pathlib import Path


def main():
    if sys.version_info < (3, 10):
        raise SystemExit('桌宠需要 Python 3.10 或更高版本。Ubuntu 22.04 / 24.04 请运行 ./setup-linux.sh，再使用 ./start-linux.sh 启动。')
    parser = argparse.ArgumentParser(description='GooglePiggy · Ubuntu 桌面小猪')
    parser.add_argument('--hook', action='store_true')
    parser.add_argument('--install', action='store_true')
    parser.add_argument('--uninstall', action='store_true')
    parser.add_argument('--apply-update', type=Path, help=argparse.SUPPRESS)
    parser.add_argument('--no-autostart', action='store_true')
    parser.add_argument('--no-hooks', action='store_true')
    parser.add_argument('--state-dir', type=Path)
    parser.add_argument('--no-observe', action='store_true', help='Do not read Codex state; use injected events only')
    parser.add_argument('--no-update-check', action='store_true')
    parser.add_argument('--qa-only', action='store_true')
    parser.add_argument('--quit-after', type=float)
    parser.add_argument('--capture', type=Path, help='Capture only this application window, for development QA')
    args = parser.parse_args()
    if args.state_dir:
        os.environ['GOOGLEPIGGY_STATE_DIR'] = str(args.state_dir.expanduser().absolute())
    if args.hook:
        from linux.hook import main as hook_main
        hook_main()
        return
    if args.apply_update:
        from linux.update_helper import apply_job
        apply_job(args.apply_update)
        return
    if args.install or args.uninstall:
        from linux.integration import install, uninstall
        uninstall() if args.uninstall else install(not args.no_autostart, not args.no_hooks)
        return
    if args.qa_only:
        from animation_clock import load_manifest
        from linux.paths import resource_root
        clips = load_manifest(resource_root())
        for clip in clips.values():
            for frame in clip.frames.specs:
                if not (resource_root()/frame['file']).is_file():
                    raise FileNotFoundError(frame['file'])
        print(json.dumps({'python': sys.version.split()[0], 'frozen': bool(getattr(sys, 'frozen', False)),
                          'animations': len(clips), 'frames': sum(len(c.frames) for c in clips.values()),
                          'source': 'unmodified upstream RGBA assets'}, ensure_ascii=False))
        return
    from linux.desktop import run
    run(args)


if __name__ == '__main__':
    main()

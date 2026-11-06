"""Real mouse and Dock checks; run only in a disposable GNOME Xorg desktop."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--app', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    if os.environ.get('GOOGLEPIGGY_ISOLATED_DESKTOP') != '1':
        raise SystemExit('Requires GOOGLEPIGGY_ISOLATED_DESKTOP=1 in a disposable desktop.')
    sys.path.insert(0, str(args.app.resolve()))
    from PySide6.QtCore import QPoint, Qt, QTimer
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QWidget
    from codex_bridge import atomic_json
    from linux.desktop import PetWindow

    def command(*values):
        return subprocess.check_output(values, text=True, timeout=5).strip()

    def desktop_alive():
        wm = re.search(r'0x[0-9a-f]+', command('xprop', '-root', '_NET_SUPPORTING_WM_CHECK'))
        assert wm and 'GNOME Shell' in command('xprop', '-id', wm[0], '_NET_WM_NAME')

    desktop_alive()
    schema = 'org.gnome.shell.extensions.dash-to-dock'
    saved = {key: command('gsettings', 'get', schema, key)
             for key in ('dock-position', 'dash-max-icon-size', 'dock-fixed')}
    app = QApplication.instance() or QApplication([])
    app.setQuitOnLastWindowClosed(False)
    assert app.platformName() == 'xcb'
    args.report.parent.mkdir(parents=True, exist_ok=True)

    def wait(predicate, timeout=5):
        deadline = time.monotonic()+timeout
        while time.monotonic() < deadline:
            QTest.qWait(50)
            if predicate():
                return
        raise AssertionError('Desktop interaction timed out')

    def mouse(*values):
        print('mouse: '+' '.join(values), flush=True)
        command('xdotool', *values)
        QTest.qWait(75)
        desktop_alive()

    def point(position):
        scale = app.primaryScreen().devicePixelRatio()
        mouse('mousemove', str(round(position.x()*scale)), str(round(position.y()*scale)))

    with tempfile.TemporaryDirectory(prefix='googlepiggy-desktop-') as directory:
        state = Path(directory)
        atomic_json(state/'settings.json', {'idleSleepSeconds': 3600, 'wakeAwakeSeconds': 3600})
        pet = PetWindow(SimpleNamespace(no_observe=True, no_update_check=True,
                                       capture=None, quit_after=None), state)
        checks = []
        try:
            wait(lambda: pet.last_pil is not None)

            def center():
                screen = pet.screens()[0]
                pet.anchor = QPoint((screen.work[0]+screen.work[2])//2,
                                    (screen.work[1]+screen.work[3])//2)
                pet.dirty = True
                QTest.qWait(150)

            def body():
                offset = pet.renderer.offset
                return pet.mapToGlobal(QPoint(round(410+offset[0]), round(500+offset[1])))

            center()
            class Underlay(QWidget):
                clicks = 0
                def mousePressEvent(self, event):
                    self.clicks += 1

            underlay = Underlay(None, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint |
                               Qt.WindowType.X11BypassWindowManagerHint)
            try:
                underlay.setGeometry(pet.geometry())
                underlay.show()
                pet.raise_()
                QTest.qWait(100)
                work = app.primaryScreen().availableGeometry()
                corners = (QPoint(8, 8), QPoint(pet.width()-9, 8),
                           QPoint(8, pet.height()-9), QPoint(pet.width()-9, pet.height()-9))
                empty = next(p for p in corners if work.contains(pet.mapToGlobal(p))
                             and pet.last_pil.getpixel((p.x(), p.y()))[3] == 0)
                point(pet.mapToGlobal(empty)); mouse('click', '1')
                assert underlay.clicks == 1, 'Transparent padding intercepted the click'
            finally:
                underlay.close()
            checks.append('transparent_click_through')
            desktop_alive()
            print(checks[-1], flush=True)

            point(body()); mouse('click', '1')
            assert pet.transient == ('flat', True)
            checks.append('body_click')
            desktop_alive()
            print(checks[-1], flush=True)
            wait(lambda: pet.transient is None, timeout=10)

            menu_seen = []
            def inspect_menu():
                popup = app.activePopupWidget()
                if popup:
                    menu_seen.extend(action.text() for action in popup.actions())
                    command('xdotool', 'key', 'Escape')
            QTimer.singleShot(500, inspect_menu)
            point(body()); mouse('click', '3')
            wait(lambda: bool(menu_seen))
            assert any('小猪习性' in label for label in menu_seen)
            checks.append('native_context_menu')
            desktop_alive()
            print(checks[-1], flush=True)

            for side in ('left', 'right', 'top', 'bottom'):
                for size, fixed in ((36, False), (72, True)):
                    for key, value in (('dock-position', side.upper()),
                                       ('dash-max-icon-size', str(size)),
                                       ('dock-fixed', str(fixed).lower())):
                        command('gsettings', 'set', schema, key, value)
                        QTest.qWait(250)
                    def dock_ready():
                        value = pet.tail.dock_settings.poll(time.monotonic())
                        return value and value[0] == side and value[1] == size+32 and value[3] == fixed
                    wait(dock_ready)
                    QTest.qWait(250)
                    for edge in ('left', 'right', 'top', 'bottom'):
                        center()
                        frame = pet.screens()[0].frame
                        x, y = (frame[0]+frame[2])//2, (frame[1]+frame[3])//2
                        target = {'left': QPoint(frame[0]+1, y), 'right': QPoint(frame[2]-2, y),
                                  'top': QPoint(x, frame[1]+1), 'bottom': QPoint(x, frame[3]-2)}[edge]
                        point(body()); mouse('mousedown', '1')
                        point(target); mouse('mouseup', '1')
                        wait(lambda: pet.hidden and pet.tail.isVisible())
                        assert pet.hidden_edge == edge
                        tail = pet.tail.geometry()
                        work = app.primaryScreen().availableGeometry()
                        assert work.contains(tail.topLeft()) and work.contains(tail.bottomRight())
                        if side == edge and fixed:
                            app.primaryScreen().grabWindow(0).save(str(args.report.with_name(args.report.stem+'-tail-'+edge+'.png')))
                        point(pet.tail.mapToGlobal(QPoint(1, 1))); mouse('click', '1')
                        wait(lambda: not pet.hidden_edge and pet.isVisible())
                        checks.append(f'dock_{side}_{size}_{fixed}_recall_{edge}')
                        desktop_alive()
                        print(checks[-1], flush=True)
            result = {'passed': True, 'gnome': command('gnome-shell', '--version'),
                      'scale': app.primaryScreen().devicePixelRatio(), 'checks': checks}
        finally:
            pet.quit()
            pet.deleteLater()
            app.processEvents()
            for key, value in saved.items():
                command('gsettings', 'set', schema, key, value)
                time.sleep(.25)
        desktop_alive()
        result['desktop_alive_after_cleanup'] = True
        args.report.write_text(json.dumps(result, indent=2)+'\n')
        print(json.dumps(result))


if __name__ == '__main__':
    main()

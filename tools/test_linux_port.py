"""Linux regression tests: real bridge processes, Qt interactions and rollback."""
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PIL import Image
from codex_bridge import atomic_json
from codex_observer import CodexObserver
from family_store import FamilyStore
from linux.geometry import Screen, fit_delta, tail_rects, touched_edge, translate
from linux.hook import handle, heartbeat_fresh, permission_summary
from linux.integration import merge_hooks, install, uninstall
from linux.paths import utc_now
from linux.update import MANIFEST, WEB, digest, extract_package, parse_releases, validate_tree
from linux.update_helper import install_transaction
from linux.x11 import alpha_rectangles

ROOT = Path(__file__).resolve().parents[1]


def wait_for(predicate, timeout=3):
    deadline = time.monotonic()+timeout
    while time.monotonic() < deadline:
        result = predicate()
        if result:
            return result
        time.sleep(.01)
    raise AssertionError('Timed out waiting for bridge state')


def package(root, number='0.5.9', contents=b'new app'):
    root.mkdir()
    executable = root/'googlepiggy'
    executable.write_bytes(contents)
    executable.chmod(0o755)
    atomic_json(root/MANIFEST, {'schema': 1, 'platform': 'linux-x86_64', 'version': number,
                              'files': {'googlepiggy': digest(executable)}})
    return root


class IntegrationTests(unittest.TestCase):
    def test_empty_xdg_variables_keep_standard_user_directories(self):
        from linux.paths import state_dir, config_dir, data_dir
        with patch.dict(os.environ, {'XDG_STATE_HOME': '', 'XDG_CONFIG_HOME': '', 'XDG_DATA_HOME': '', 'GOOGLEPIGGY_STATE_DIR': ''}):
            self.assertEqual(state_dir(), Path.home()/'.local/state/googlepiggy')
            self.assertEqual(config_dir(), Path.home()/'.config')
            self.assertEqual(data_dir(), Path.home()/'.local/share')

    def test_registration_preserves_other_handlers_and_unknown_events(self):
        existing = {'description': 'user config', 'hooks': {'Stop': [{'matcher': '*', 'hooks': [
                    {'type': 'command', 'command': 'other-tool'},
                    {'type': 'command', 'command': 'old --hook', 'statusMessage': 'GooglePiggy Linux'}]}],
                    'CustomEvent': [{'hooks': [{'type': 'command', 'command': 'custom'}]}]}}
        merged = merge_hooks(existing, 'new --hook')
        self.assertEqual(merged['hooks']['Stop'][0]['hooks'], [{'type': 'command', 'command': 'other-tool'}])
        self.assertEqual(merged['hooks']['CustomEvent'], existing['hooks']['CustomEvent'])
        self.assertEqual(merged, merge_hooks(merged, 'new --hook'))
        removed = merge_hooks(merged)
        self.assertEqual(removed['hooks']['Stop'][0]['hooks'], [{'type': 'command', 'command': 'other-tool'}])
        self.assertEqual(len(removed['hooks']), 2)

    def test_invalid_config_is_not_replaced(self):
        for value in [[], {'hooks': []}, {'hooks': {'Stop': {}}}]:
            with self.assertRaises(ValueError):
                merge_hooks(value, 'new --hook')

    def test_install_uninstall_with_existing_hooks_and_unicode_path(self):
        with tempfile.TemporaryDirectory(prefix='pig-中文-') as tmp:
            root = Path(tmp)
            env = {'CODEX_HOME': str(root/'codex'), 'GOOGLEPIGGY_STATE_DIR': str(root/'state'),
                   'XDG_CONFIG_HOME': str(root/'config'), 'XDG_DATA_HOME': str(root/'data')}
            with patch.dict(os.environ, env):
                hookfile = root/'codex/hooks.json'
                original = {'hooks': {'Stop': [{'hooks': [{'type': 'command', 'command': 'keep me'}]}]}}
                atomic_json(hookfile, original)
                install()
                first = json.loads(hookfile.read_text())
                install()
                self.assertEqual(first, json.loads(hookfile.read_text()))
                self.assertTrue(list((root/'state/hook-backups').glob('*.json')))
                self.assertTrue((root/'config/autostart/googlepiggy-linux.desktop').is_file())
                launcher = root/'data/applications/googlepiggy-linux.desktop'
                subprocess.run(['desktop-file-validate', str(launcher)], check=True)
                uninstall()
                self.assertEqual(original, json.loads(hookfile.read_text()))
                self.assertFalse(launcher.exists())
                self.assertTrue((root/'state').is_dir())


class HookTests(unittest.TestCase):
    def test_real_hook_process_does_not_import_qt(self):
        with tempfile.TemporaryDirectory() as tmp:
            code = "import sys,linux_pet;sys.argv=['linux_pet','--hook','--state-dir',sys.argv[1]];linux_pet.main();assert not any(x.startswith('PySide6') for x in sys.modules)"
            result = subprocess.run([sys.executable, '-c', code, tmp], input=json.dumps(
                {'hook_event_name': 'UserPromptSubmit', 'session_id': 'root', 'turn_id': 'turn', 'prompt': '中文任务'}),
                text=True, capture_output=True, cwd=ROOT, timeout=5, check=True)
            self.assertEqual(json.loads(result.stdout), {})
            self.assertEqual(len(list((Path(tmp)/'family-events').glob('*.json'))), 1)

    def test_multitask_child_lifecycle_is_actor_scoped(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            def event(name, session, agent=''):
                handle({'hook_event_name': name, 'session_id': session, 'agent_id': agent, 'turn_id': 'turn'}, root)
            event('UserPromptSubmit', 'A')
            event('UserPromptSubmit', 'B')
            event('SubagentStart', 'A', 'child')
            event('SubagentStop', 'A', 'child')
            observer = CodexObserver(FamilyStore(), root, home=root, enabled=False)
            observer.poll()
            self.assertTrue(observer.store.nodes['A'].active)
            self.assertTrue(observer.store.nodes['B'].active)
            self.assertFalse(observer.store.nodes['child'].active)
            self.assertEqual(observer.store.nodes['child'].parent, 'A')

    def test_no_live_window_returns_native_permission_flow(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = handle({'hook_event_name': 'PermissionRequest', 'session_id': 'A', 'tool_name': 'Bash', 'tool_input': {'command': 'example'}}, root, .1)
            self.assertEqual(result, {})
            self.assertFalse((root/'permission-requests').exists())

    def test_missing_details_do_not_offer_blanket_approval(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            atomic_json(root/'pig-heartbeat.json', {'pid': os.getpid(), 'updated_at': utc_now()})
            self.assertTrue(heartbeat_fresh(root))
            self.assertEqual(handle({'hook_event_name': 'PermissionRequest', 'session_id': 'A'}, root, .1), {})

    def test_permission_decisions_and_mismatched_response(self):
        for decision in ('allow', 'deny', 'wrong-id'):
            with self.subTest(decision=decision), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                atomic_json(root/'pig-heartbeat.json', {'pid': os.getpid(), 'updated_at': utc_now()})
                result = []
                thread = threading.Thread(target=lambda: result.append(handle({'hook_event_name': 'PermissionRequest',
                    'session_id': 'A', 'turn_id': 't', 'tool_name': 'Bash', 'tool_input': {'command': 'example'}}, root, 2)))
                thread.start()
                request = wait_for(lambda: list((root/'permission-requests').glob('*.request.json')))[0]
                value = json.loads(request.read_text())
                atomic_json(request.with_name(value['request_id']+'.response.json'),
                            {'request_id': 'wrong' if decision == 'wrong-id' else value['request_id'],
                             'decision': 'allow' if decision == 'wrong-id' else decision})
                thread.join(3)
                self.assertFalse(thread.is_alive())
                if decision == 'wrong-id':
                    self.assertEqual(result, [{}])
                else:
                    self.assertEqual(result[0]['hookSpecificOutput']['decision']['behavior'], decision)
                self.assertFalse(list((root/'permission-requests').glob('*.request.json')))

    def test_permission_timeout_cleans_up_without_approval(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            atomic_json(root/'pig-heartbeat.json', {'pid': os.getpid(), 'updated_at': utc_now()})
            result = handle({'hook_event_name': 'PermissionRequest', 'session_id': 'A',
                             'tool_name': 'Bash', 'tool_input': {'command': 'example'}}, root, .01)
            self.assertEqual(result, {})
            self.assertFalse(list((root/'permission-requests').glob('*.request.json')))

    def test_old_permission_response_cannot_approve_or_overwrite_new_turn(self):
        from codex_bridge import actor_path
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            atomic_json(root/'pig-heartbeat.json', {'pid': os.getpid(), 'updated_at': utc_now()})
            result = []
            thread = threading.Thread(target=lambda: result.append(handle({'hook_event_name': 'PermissionRequest',
                'session_id': 'A', 'turn_id': 'old-turn', 'tool_name': 'Bash', 'tool_input': {'command': 'example'}}, root, 2)))
            thread.start()
            request = wait_for(lambda: list((root/'permission-requests').glob('*.request.json')))[0]
            value = json.loads(request.read_text())
            wait_for(lambda: (json.loads(actor_path(root, 'A').read_text()) if actor_path(root, 'A').is_file() else {}).get('event') == 'PermissionRequest')
            handle({'hook_event_name': 'UserPromptSubmit', 'session_id': 'A', 'turn_id': 'new-turn'}, root)
            atomic_json(request.with_name(value['request_id']+'.response.json'), {'request_id': value['request_id'], 'decision': 'allow'})
            thread.join(3)
            self.assertEqual(result, [{}])
            self.assertEqual(json.loads(actor_path(root, 'A').read_text())['turn_id'], 'new-turn')

    def test_permission_summary_redacts_secrets(self):
        summary = permission_summary({'tool_name': 'Bash', 'tool_input': {'command': 'token=secret123 password=xyz'}})
        self.assertNotIn('secret123', summary)
        self.assertNotIn('xyz', summary)
        summary = permission_summary({'tool_name': 'MCP', 'tool_input': {'token': 'json-secret'}})
        self.assertNotIn('json-secret', summary)


class GeometryTests(unittest.TestCase):
    def test_screen_seam_is_not_a_hiding_edge(self):
        left = Screen((-1920, 0, 0, 1080), (-1850, 24, 0, 1080))
        right = Screen((0, 0, 1920, 1080), (70, 24, 1920, 1080))
        self.assertIsNone(touched_edge((-152, 400, 0, 570), left, [left, right]))
        self.assertEqual(touched_edge((-1920, 400, -1768, 570), left, [left, right]), 'left')

    def test_visible_content_fits_negative_origin_work_area(self):
        work = (-1850, 24, 0, 1080)
        rect = (-1980, -20, -1650, 300)
        fitted = translate(rect, *fit_delta(rect, work))
        self.assertGreaterEqual(fitted[0], work[0])
        self.assertGreaterEqual(fitted[1], work[1])

    def test_tail_group_stays_clear_of_panel_at_all_scales(self):
        screen = Screen((0, 0, 1920, 1080), (70, 24, 1920, 1080))
        for edge in ('left', 'right', 'top', 'bottom'):
            for scale in (.5, 1, 2):
                rects = tail_rects(edge, screen, (0, 0), 3, scale)
                self.assertEqual(len(rects), 4)
                if edge in ('left', 'right'):
                    self.assertGreaterEqual(min(r[1] for r in rects), screen.work[1])
                    self.assertLessEqual(max(r[3] for r in rects), screen.work[3])
                else:
                    self.assertGreaterEqual(min(r[0] for r in rects), screen.work[0])
                    self.assertLessEqual(max(r[2] for r in rects), screen.work[2])

    def test_input_rectangles_cover_visible_pixels_without_empty_canvas(self):
        image = Image.new('RGBA', (8, 8))
        image.putpixel((2, 3), (255, 0, 0, 255))
        image.putpixel((3, 3), (255, 0, 0, 128))
        self.assertEqual(alpha_rectangles(image), [[2, 3, 2, 1]])
        self.assertEqual(image.getpixel((3, 3))[3], 128)


class UpdateTests(unittest.TestCase):
    def test_only_verified_linux_channel_is_selected(self):
        number, tag = '0.5.10', 'v0.5.10-linux'
        name = f'GooglePiggy-{number}-linux-x86_64.tar.gz'
        row = {'draft': False, 'prerelease': False, 'tag_name': tag, 'html_url': WEB+'tag/'+tag,
               'assets': [{'name': name, 'browser_download_url': WEB+'download/'+tag+'/'+name,
                           'size': 123, 'digest': 'sha256:'+'a'*64}]}
        self.assertEqual(parse_releases([row])[0].version, number)
        row['assets'][0]['digest'] = ''
        self.assertEqual(parse_releases([row]), [])
        row['tag_name'] = 'v0.5.10-windows'
        self.assertEqual(parse_releases([row]), [])

    def test_package_validation_detects_tampering_and_extra_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = package(Path(tmp)/'package')
            validate_tree(root, '0.5.9')
            (root/'googlepiggy').write_bytes(b'tampered')
            with self.assertRaises(ValueError):
                validate_tree(root, '0.5.9')
            (root/'googlepiggy').write_bytes(b'new app')
            (root/'nested').mkdir()
            (root/'nested'/MANIFEST).write_text('{}')
            with self.assertRaises(ValueError):
                validate_tree(root, '0.5.9')

    def test_archive_traversal_and_symlinks_are_rejected(self):
        for name, link in [('../escape', False), ('symlink', True)]:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                archive = Path(tmp)/'bad.tar.gz'
                with tarfile.open(archive, 'w:gz') as output:
                    member = tarfile.TarInfo(name)
                    if link:
                        member.type, member.linkname = tarfile.SYMTYPE, '/tmp/escape'
                        output.addfile(member)
                    else:
                        member.size = 1
                        output.addfile(member, io.BytesIO(b'x'))
                with self.assertRaises(ValueError):
                    extract_package(archive, Path(tmp)/'out', '0.5.9')
                self.assertFalse((Path(tmp)/'escape').exists())

    def test_valid_archive_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            candidate = package(root/'package')
            archive = root/'good.tar.gz'
            with tarfile.open(archive, 'w:gz') as output:
                for file in candidate.iterdir():
                    output.add(file, arcname=file.name)
            extract_package(archive, root/'out', '0.5.9')
            self.assertEqual((root/'out/googlepiggy').read_bytes(), b'new app')

    def test_failed_update_restores_and_relaunches_original(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = package(root/'installed', contents=b'old app')
            candidate = package(root/'candidate')
            launches, stopped = [], []
            def launch(folder):
                launches.append((folder/'googlepiggy').read_bytes())
                return len(launches)
            with self.assertRaises(RuntimeError):
                install_transaction(target, candidate, '0.5.9', launch, lambda child, number: False, stopped.append)
            self.assertEqual((target/'googlepiggy').read_bytes(), b'old app')
            self.assertEqual(launches, [b'new app', b'old app'])
            self.assertEqual(stopped, [1])

    def test_successful_update_keeps_backup(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = package(root/'installed', contents=b'old app')
            candidate = package(root/'candidate')
            backup = install_transaction(target, candidate, '0.5.9', lambda folder: 1,
                                         lambda child, number: True, lambda child: None)
            self.assertEqual((backup/'googlepiggy').read_bytes(), b'old app')
            self.assertEqual((target/'googlepiggy').read_bytes(), b'new app')

    def test_staging_failure_keeps_original_and_removes_partial_stage(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = package(root/'installed', contents=b'old app')
            candidate = package(root/'candidate')
            def fail_copy(source, destination, **kwargs):
                destination.mkdir()
                (destination/'partial').write_bytes(b'x')
                raise OSError('simulated disk full')
            with patch('linux.update_helper.shutil.copytree', side_effect=fail_copy), self.assertRaises(OSError):
                install_transaction(target, candidate, '0.5.9', lambda folder: None, lambda child, version: True, lambda child: None)
            self.assertEqual((target/'googlepiggy').read_bytes(), b'old app')
            self.assertEqual(list(root.glob('.googlepiggy-stage-*')), [])


class QtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setQuitOnLastWindowClosed(False)

    def setUp(self):
        from linux.desktop import PetWindow
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.args = SimpleNamespace(no_observe=True, no_update_check=True, capture=None, quit_after=None)
        self.window = PetWindow(self.args, self.root)
        self.window.timer.stop()
        self.app.processEvents()

    def tearDown(self):
        self.window.quit()
        self.window.deleteLater()
        self.app.processEvents()
        self.tmp.cleanup()

    def dispatch(self, event, session='A', agent=''):
        handle({'hook_event_name': event, 'session_id': session, 'agent_id': agent, 'turn_id': 't'}, self.root)
        self.window.now, self.window.wall = time.monotonic(), time.time()
        self.window.poll()
        self.window.resolve_visual()
        self.window.dirty = True
        self.window.tick()

    def test_click_plays_flat_and_drag_moves_the_family(self):
        from PySide6.QtCore import QPoint, Qt
        from PySide6.QtTest import QTest
        w = self.window
        offset = w.renderer.offset
        body = QPoint(round(410+offset[0]), round(500+offset[1]))
        QTest.mouseClick(w, Qt.MouseButton.LeftButton, pos=body)
        self.assertEqual(w.transient, ('flat', True))
        before = QPoint(w.anchor)
        QTest.mousePress(w, Qt.MouseButton.LeftButton, pos=body)
        QTest.mouseMove(w, body+QPoint(30, 20))
        self.assertTrue(w.dragging)
        QTest.mouseRelease(w, Qt.MouseButton.LeftButton, pos=body+QPoint(30, 20))
        self.assertFalse(w.dragging)
        self.assertNotEqual(w.anchor, before)

    def test_qt_void_bindings_do_not_consume_none_references(self):
        # Non-immortal CPython singletons require an owned return reference.
        # Short visual smoke tests miss the eventual none_dealloc process abort.
        import gc
        from PySide6.QtGui import QImage, QPainter
        image = QImage(8, 8, QImage.Format.Format_RGBA8888)
        source = QImage(8, 8, QImage.Format.Format_RGBA8888)
        painter = QPainter(image)
        try:
            for _ in range(5):
                painter.drawImage(0, 0, source)
            gc.collect()
            before = sys.getrefcount(None)
            for _ in range(200):
                painter.drawImage(0, 0, source)
            gc.collect()
            after = sys.getrefcount(None)
            self.assertGreaterEqual(after-before, -2)
        finally:
            painter.end()

    def test_three_visible_children_and_independent_chat_clocks(self):
        self.dispatch('UserPromptSubmit')
        for i in range(5):
            self.dispatch('SubagentStart', agent=f'child-{i}')
        self.assertEqual(len(self.window.store.children('A', time.time())), 5)
        self.assertEqual(len(self.window.renderer.child_rects), 3)
        first_epoch = self.window.clock.tracks['A'].epoch
        self.dispatch('UserPromptSubmit', 'B')
        self.window.store.select('A')
        self.assertEqual(self.window.clock.tracks['A'].epoch, first_epoch)
        self.assertEqual(self.window.store.selected, 'A')

    def test_hidden_family_waits_for_children_and_ignores_other_chat(self):
        from PySide6.QtCore import QPoint
        self.dispatch('UserPromptSubmit')
        self.dispatch('SubagentStart', agent='child')
        w = self.window
        screen = w.screens()[0]
        w.anchor = QPoint(screen.frame[0]+410-w.renderer.pet_bounds[0], w.anchor.y())
        self.assertTrue(w.hide_at_edge())
        w.now += .6
        w.advance_transition()
        self.assertTrue(w.hidden)
        self.assertTrue(w.tail.isVisible())
        self.dispatch('UserPromptSubmit', 'B')
        self.assertTrue(w.hidden)
        self.assertEqual(w.store.selected, 'A')
        self.dispatch('Stop')
        self.assertTrue(w.hidden)
        self.dispatch('SubagentStop', agent='child')
        self.assertFalse(w.hidden)
        self.assertEqual(w.reveal_completion, 'A')
        w.now += .6
        w.advance_transition()
        w.resolve_visual()
        self.assertEqual(w.celebration_family, 'A')
        self.assertEqual(w.position[0], 'jump')

    def test_tail_click_reveals_early(self):
        from PySide6.QtCore import QPoint, Qt
        from PySide6.QtTest import QTest
        w = self.window
        screen = w.screens()[0]
        w.anchor = QPoint(screen.frame[0]+410-w.renderer.pet_bounds[0], w.anchor.y())
        self.assertTrue(w.hide_at_edge())
        w.now += .6
        w.advance_transition()
        QTest.mouseClick(w.tail, Qt.MouseButton.LeftButton, pos=QPoint(20, 20))
        self.assertFalse(w.hidden)
        self.assertEqual(w.transition[0], 'reveal')

    def test_appearance_preview_saves_without_creating_tasks(self):
        from PySide6.QtWidgets import QCheckBox
        w = self.window
        w.show_appearance()
        for checkbox in w.appearance_dialog.findChildren(QCheckBox):
            checkbox.setChecked(True)
        w.appearance_dialog.sliders['petScale'].setValue(80)
        w.tick()
        w.save_settings()
        self.assertTrue(w.preview_dialog and w.preview_task)
        self.assertIsNotNone(w.renderer.permission_rect)
        self.assertIsNotNone(w.renderer.selector_rect)
        self.assertFalse(w.renderer.buttons)
        self.assertEqual(w.store.nodes, {})
        self.assertAlmostEqual(json.loads((self.root/'appearance.json').read_text())['petScale'], .8)
        w.appearance_dialog.close()
        self.assertFalse(w.preview_dialog or w.preview_task)

    def test_long_permission_real_hook_requires_scroll_before_allow(self):
        from PySide6.QtCore import QPoint, Qt
        from PySide6.QtTest import QTest
        w = self.window
        w.heartbeat(force=True)
        payload = {'hook_event_name': 'PermissionRequest', 'session_id': 'permission-test', 'turn_id': 't',
                   'tool_name': 'Bash', 'tool_input': {'command': '显示完整操作详情 '+('这是很长的中文路径与操作说明。'*80)}}
        proc = subprocess.Popen([sys.executable, str(ROOT/'linux_pet.py'), '--hook', '--state-dir', str(self.root)],
                                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            proc.stdin.write(json.dumps(payload, ensure_ascii=False).encode())
            proc.stdin.close()
            wait_for(lambda: list((self.root/'permission-requests').glob('*.request.json')))
            w.poll()
            w.dirty = True
            w.tick()
            self.assertIsNotNone(w.permission)
            request_id = w.permission['request_id']
            w.permission_decision('allow')
            self.assertFalse((self.root/'permission-requests'/(request_id+'.response.json')).exists())
            w.permission_page = 10000
            w.dirty = True
            w.tick()
            self.assertIn(request_id, w.permission_viewed)
            rect = w.renderer.buttons['allow']
            point = QPoint(round((rect[0]+rect[2])/2+w.renderer.offset[0]), round((rect[1]+rect[3])/2+w.renderer.offset[1]))
            QTest.mouseClick(w, Qt.MouseButton.LeftButton, pos=point)
            proc.wait(timeout=3)
            output = json.loads(proc.stdout.read())
            self.assertEqual(output['hookSpecificOutput']['decision']['behavior'], 'allow')
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait()
            proc.stdout.close()
            proc.stderr.close()

    def test_failed_chat_open_keeps_unread_indicator(self):
        self.dispatch('UserPromptSubmit')
        self.dispatch('Stop')
        with patch('linux.desktop.QDesktopServices.openUrl', return_value=False), patch('linux.desktop.QMessageBox.information'):
            self.window.open_thread('A')
        self.assertTrue(self.window.store.nodes['A'].unread)

    def test_pending_permission_is_stable_and_child_click_changes_focus(self):
        from datetime import datetime, timezone
        from PySide6.QtCore import QPoint, Qt
        from PySide6.QtTest import QTest
        self.dispatch('UserPromptSubmit')
        self.dispatch('SubagentStart', agent='child')
        def request(request_id, agent):
            atomic_json(self.root/'permission-requests'/(request_id+'.request.json'),
                        {'request_id': request_id, 'session_id': 'A', 'agent_id': agent, 'turn_id': 't',
                         'expires_at': datetime.fromtimestamp(time.time()+500, timezone.utc).isoformat(),
                         'created_at': utc_now(), 'hook_pid': os.getpid(), 'summary': '演示权限详情'})
        w = self.window
        request('b'*32, 'child')
        w.poll()
        self.assertEqual(w.permission['request_id'], 'b'*32)
        request('a'*32, '')
        w.poll()
        self.assertEqual(w.permission['request_id'], 'b'*32)
        w.permission = None
        w.poll()
        self.assertEqual(w.permission['request_id'], 'a'*32)
        w.dirty = True
        w.tick()
        rect = w.renderer.child_rects['child']
        point = QPoint(round((rect[0]+rect[2])/2+w.renderer.offset[0]), round((rect[1]+rect[3])/2+w.renderer.offset[1]))
        QTest.mouseClick(w, Qt.MouseButton.LeftButton, pos=point)
        self.assertEqual(w.permission['request_id'], 'b'*32)

    def test_packaged_chat_opener_does_not_export_bundled_runtime(self):
        from linux.desktop import PetWindow
        env = {'LD_LIBRARY_PATH': '/bundled/qt', 'LD_LIBRARY_PATH_ORIG': '/original/lib',
               'QT_PLUGIN_PATH': '/bundled/plugins', 'PYTHONHOME': '/bundled/python'}
        with patch.object(sys, 'frozen', True, create=True), patch.dict(os.environ, env), \
             patch('linux.desktop.subprocess.run', return_value=SimpleNamespace(returncode=0)) as runner:
            self.assertTrue(PetWindow.open_url('codex://threads/test'))
            passed = runner.call_args.kwargs['env']
            self.assertEqual(passed['LD_LIBRARY_PATH'], '/original/lib')
            self.assertNotIn('QT_PLUGIN_PATH', passed)
            self.assertNotIn('PYTHONHOME', passed)

    def test_saved_scale_cold_start_keeps_artwork_inside_work_area(self):
        from linux.desktop import PetWindow
        for scale in (.5, .8, 1, 2):
            with self.subTest(scale=scale):
                folder = self.root/str(scale)
                folder.mkdir()
                atomic_json(folder/'appearance.json', {'petScale': scale})
                atomic_json(folder/'position.json', {'anchor': [100000, 100000]})
                window = PetWindow(self.args, folder)
                window.timer.stop()
                try:
                    bounds = window.visible_global()
                    work = window.screens()[0].work
                    self.assertGreaterEqual(bounds[0], work[0])
                    self.assertGreaterEqual(bounds[1], work[1])
                    self.assertLessEqual(bounds[2], work[2])
                    self.assertLessEqual(bounds[3], work[3])
                finally:
                    window.quit()
                    window.deleteLater()


if __name__ == '__main__':
    unittest.main()

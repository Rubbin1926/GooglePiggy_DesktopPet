"""Qt/X11 desktop adapter; upstream state and animation modules remain unchanged."""
import fcntl
import os
import queue
import subprocess
import sys
import time
from datetime import datetime

from PIL import Image
from PySide6.QtCore import QPoint, Qt, QTimer, QUrl
from PySide6.QtGui import QActionGroup, QColor, QCursor, QDesktopServices, QFont, QFontDatabase, QIcon, QImage, QPainter
from PySide6.QtWidgets import (QApplication, QCheckBox, QColorDialog, QDialog, QFormLayout,
                              QHBoxLayout, QLabel, QMenu, QMessageBox, QPushButton, QSlider, QVBoxLayout, QWidget)

from animation_clock import AnimationClock, load_manifest
from appearance import Appearance, COLORS, RANGES
from codex_bridge import atomic_json
from codex_observer import CodexObserver
from family_store import FamilyStore
from leisure import Leisure
from update_notice import UpdateNotice
from linux import VERSION
from linux.geometry import Screen, fit_delta, inside, intersection, tail_rects, touched_edge, translate, union
from linux.integration import autostart_enabled, set_autostart
from linux.paths import app_root, approval_mode, font_file, pid_alive, read_json, resource_root, state_dir, utc_now
from linux.render import Renderer, resize
from linux.update import Updater
from linux.x11 import InputShape

FLAGS = Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.WindowDoesNotAcceptFocus


def screen_rect(rect):
    return rect.x(), rect.y(), rect.x()+rect.width(), rect.y()+rect.height()


def qimage(image):
    return QImage(image.tobytes(), image.width, image.height, image.width*4, QImage.Format.Format_RGBA8888).copy()


class TailWindow(QWidget):
    def __init__(self, pet):
        super().__init__(None, FLAGS)
        self.pet = pet
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setWindowTitle('GooglePiggy · 尾巴')
        self.image = QImage()

    def refresh(self):
        pet = self.pet
        count = min(3, len(pet.store.children(pet.store.selected, pet.wall)))
        rects = tail_rects(pet.hidden_edge, pet.hidden_screen, tuple(pet.home_anchor.toTuple()), count, pet.appearance.petScale)
        bounds = union(rects)
        image = Image.new('RGBA', (bounds[2]-bounds[0], bounds[3]-bounds[1]))
        source = pet.tails[pet.hidden_edge]
        for rect in rects:
            sprite = resize(source, (rect[2]-rect[0], rect[3]-rect[1]))
            image.alpha_composite(sprite, (rect[0]-bounds[0], rect[1]-bounds[1]))
        self.image = qimage(image)
        self.setGeometry(bounds[0], bounds[1], image.width, image.height)
        self.show()
        pet.input_shape.apply(self, image)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.drawImage(0, 0, self.image)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.pet.reveal()

    def contextMenuEvent(self, event):
        self.pet.menu(event.globalPos())


class AppearanceDialog(QDialog):
    def __init__(self, pet):
        super().__init__(None, Qt.WindowType.Dialog | Qt.WindowType.WindowStaysOnTopHint)
        self.pet, self.sliders, self.labels, self.colors = pet, {}, {}, {}
        self.setWindowTitle('猪猪桌宠 · 外观')
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        layout = QVBoxLayout(self)
        title = QLabel('调整外观')
        title.setStyleSheet('font-size:20px; font-weight:600; margin:6px')
        layout.addWidget(title)
        form = QFormLayout()
        layout.addLayout(form)
        names = ['猪猪大小', '对话框大小', '任务栏大小', '对话框背景不透明度', '按钮底色不透明度', '任务栏背景不透明度', '对话框上下距离', '任务栏与猪猪距离']
        for key, label in zip(RANGES, names):
            low, high, default = RANGES[key]
            factor = 1 if key.endswith('Gap') else 100
            slider = QSlider(Qt.Orientation.Horizontal)
            slider.setRange(round(low*factor), round(high*factor))
            slider.setValue(round(pet.appearance.values[key]*factor))
            slider.setMinimumWidth(220)
            display = QLabel()
            display.setMinimumWidth(55)
            row = QHBoxLayout()
            row.addWidget(slider)
            row.addWidget(display)
            form.addRow(label, row)
            self.sliders[key], self.labels[key] = slider, display
            slider.valueChanged.connect(lambda value, k=key, f=factor: self.changed(k, value/f))
            self.display(key)
        names = ['对话框背景颜色', '任务栏背景颜色', '对话框文字颜色', '按钮文字颜色', '任务栏文字颜色']
        for key, label in zip(COLORS, names):
            button = QPushButton(pet.appearance.values[key] or '默认')
            button.clicked.connect(lambda checked=False, k=key: self.choose(k))
            self.colors[key] = button
            form.addRow(label, button)
        for key, label in [('dialog', '在猪猪旁预览对话框'), ('task', '在猪猪旁预览任务栏')]:
            check = QCheckBox(label)
            check.toggled.connect(lambda value, k=key: self.preview(k, value))
            layout.addWidget(check)
        note = QLabel('即时保存 · 预览不会创建任务或发送权限决定')
        note.setStyleSheet('color:#70666b; margin-top:8px')
        layout.addWidget(note)
        reset = QPushButton('恢复默认外观')
        reset.clicked.connect(self.reset)
        layout.addWidget(reset)
        self.setMinimumWidth(460)

    def display(self, key):
        value = self.pet.appearance.values[key]
        self.labels[key].setText(f'{value:.0f}' if key.endswith('Gap') else f'{value:.0%}')

    def changed(self, key, value):
        self.pet.appearance.update({key: value})
        self.display(key)
        self.pet.appearance_changed()

    def choose(self, key):
        color = QColorDialog.getColor(QColor(self.pet.appearance.values[key] or '#fdf9f6'), self, '选择颜色')
        if color.isValid():
            self.pet.appearance.update({key: color.name()})
            self.colors[key].setText(color.name())
            self.pet.appearance_changed()

    def preview(self, key, value):
        setattr(self.pet, 'preview_'+key, value)
        self.pet.dirty = True
        self.pet.fit_next_frame = True

    def reset(self):
        self.pet.appearance.update(Appearance().values)
        for key, slider in self.sliders.items():
            slider.blockSignals(True)
            slider.setValue(round(self.pet.appearance.values[key]*(1 if key.endswith('Gap') else 100)))
            slider.blockSignals(False)
            self.display(key)
        for button in self.colors.values():
            button.setText('默认')
        self.pet.appearance_changed()

    def closeEvent(self, event):
        self.pet.preview_dialog = self.pet.preview_task = False
        self.pet.appearance_dialog = None
        self.pet.dirty = True
        super().closeEvent(event)


class PetWindow(QWidget):
    def __init__(self, args, directory):
        super().__init__(None, FLAGS)
        self.args, self.directory = args, directory
        self.version = VERSION
        self.setWindowTitle('GooglePiggy 小猪桌宠')
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setMouseTracking(True)
        self.animations = load_manifest(resource_root())
        self.store = FamilyStore()
        self.observer = CodexObserver(self.store, directory, enabled=not args.no_observe)
        if not args.no_observe:
            self.observer.enable_background()
        self.clock = AnimationClock(self.animations)
        self.now, self.wall = time.monotonic(), time.time()
        self.leisure = Leisure(self.now)
        self.appearance = Appearance(directory/'appearance.json')
        self.approval_mode = approval_mode(directory)
        self.renderer = Renderer(resource_root(), self.animations)
        self.input_shape = InputShape(QApplication.platformName() == 'xcb')
        self.tails = {edge: Image.open(resource_root()/'edge-tail'/(edge+'.png')).convert('RGBA') for edge in ('left', 'right', 'top', 'bottom')}
        self.tail = TailWindow(self)
        self.anchor, self.home_anchor = QPoint(), QPoint()
        self.hidden = False
        self.hidden_edge = self.hidden_family = self.reveal_completion = ''
        self.hidden_screen = None
        self.hidden_since = 0
        self.hidden_tokens, self.known_work = set(), set()
        self.transition = None
        self.celebration_family, self.celebration_started = '', 0
        self.position = ('idle', 0)
        self.idle_epoch = self.visual_epoch = self.now
        self.transient = None
        self.dragging, self.mouse_down, self.drag_direction = False, False, -1
        self.drag_start = self.drag_anchor = None
        self.click_action = None
        self.child_positions = {}
        self.selector_visible, self.selector_scroll, self.last_hover = False, 0, 0
        self.focused_child = ''
        self.permission = None
        self.permission_actors, self.permission_viewed = set(), set()
        self.permission_page, self.permission_epoch = 0, self.now
        self.preview_dialog = self.preview_task = False
        self.appearance_dialog = None
        self.notice, self.update_package = None, None
        self.updater = Updater(VERSION, directory/'updates')
        self.image, self.last_pil = QImage(), None
        self.dirty, self.fit_next_frame = True, True
        self.last_poll = self.last_heartbeat = 0
        self.last_signature = None
        self.last_error = ''
        self.frames_rendered = 0
        self.save_timer = QTimer(self)
        self.save_timer.setSingleShot(True)
        self.save_timer.timeout.connect(self.save_settings)
        self.timer = QTimer(self)
        self.timer.setTimerType(Qt.TimerType.PreciseTimer)
        self.timer.setInterval(20)
        self.timer.timeout.connect(self.tick)
        self._load_position()
        self.tick()
        self.show()
        self.timer.start()
        if not args.no_update_check:
            QTimer.singleShot(4000, self.updater.check)
        if args.capture:
            QTimer.singleShot(800, lambda: self.capture(args.capture))
        if args.quit_after is not None:
            QTimer.singleShot(max(1, round(args.quit_after*1000)), self.quit)

    def screens(self):
        return [Screen(screen_rect(screen.geometry()), screen_rect(screen.availableGeometry())) for screen in QApplication.screens()]

    def _load_position(self):
        work = self.screens()[0].work
        value = read_json(self.directory/'position.json') or {}
        anchor = value.get('anchor')
        if isinstance(anchor, list) and len(anchor) == 2 and all(type(v) is int for v in anchor):
            self.anchor = QPoint(*anchor)
        else:
            self.anchor = QPoint(work[2]-150, work[3]-70)
        self.home_anchor = QPoint(self.anchor)

    def save_settings(self):
        self.appearance.save()
        anchor = self.home_anchor if self.hidden_edge else self.anchor
        atomic_json(self.directory/'position.json', {'anchor': list(anchor.toTuple())})

    def appearance_changed(self):
        self.dirty = self.fit_next_frame = True
        self.save_timer.start(250)
        if self.hidden:
            self.tail.refresh()

    def show_appearance(self):
        if self.appearance_dialog is None:
            self.appearance_dialog = AppearanceDialog(self)
        self.appearance_dialog.show()
        self.appearance_dialog.raise_()
        self.appearance_dialog.activateWindow()

    def belongs_to_hidden(self, node):
        seen = set()
        while node.parent and node.id not in seen:
            seen.add(node.id)
            if node.parent == self.hidden_family:
                return True
            node = self.store.nodes.get(node.parent)
            if node is None:
                break
        return False

    def should_reveal(self):
        if self.hidden_family:
            node = self.store.nodes.get(self.hidden_family)
            return bool(node and not node.active and node.status == 'success' and
                        node.payload.get('event') in {'Stop', 'TaskCompleteFallback'} and
                        node.completion is not None and node.completion > self.hidden_since and
                        not any(n.active for n in self.store.nodes.values() if self.belongs_to_hidden(n)))
        return bool(self.permission or self.store.work_tokens()-self.hidden_tokens)

    def poll(self):
        self.observer.poll()
        pinned = self.hidden_family or self.reveal_completion
        if self.celebration_family:
            node = self.store.nodes.get(self.celebration_family)
            if self.now-self.celebration_started < self.animations['jump'].total_duration/1000 and node and not node.active:
                pinned = pinned or self.celebration_family
            else:
                self.celebration_family = ''
        if pinned:
            self.store.select(pinned)
        tokens = self.store.work_tokens()
        if tokens-self.known_work:
            self.leisure.reset(self.now)
            if not self.dragging and not self.transition:
                self.transient = None
        self.known_work |= tokens
        self.sync_permissions()
        for node in self.store.nodes.values():
            visual = 'question' if node.id in self.permission_actors else self.store.visual(node, self.wall)
            parent = self.store.nodes.get(node.parent)
            changed = max(node.changed, parent.changed) if parent and self.store.paused(node) else node.changed
            self.clock.update(node.id, node.turn, visual, self.now, max(0, self.wall-changed))
        if self.hidden_edge and self.should_reveal():
            self.reveal(completed=bool(self.hidden_family))
        if self.hidden:
            self.tail.refresh()
        self.dirty = True

    def sync_permissions(self):
        pending = {}
        folder = self.directory/'permission-requests'
        for path in sorted(folder.glob('*.request.json')):
            value = read_json(path)
            if not isinstance(value, dict):
                continue
            request_id = value.get('request_id', '')
            if not isinstance(request_id, str) or len(request_id) != 32 or any(c not in '0123456789abcdef' for c in request_id):
                continue
            if path.name != request_id+'.request.json':
                continue
            actor = value.get('agent_id') or value.get('session_id')
            node = self.store.nodes.get(actor)
            try:
                expired = datetime.fromisoformat(value['expires_at'].replace('Z', '+00:00')).timestamp() < self.wall
            except (KeyError, TypeError, ValueError):
                expired = True
            stale = node and (node.status == 'interrupted' or node.completion is not None or
                              value.get('turn_id') and node.turn and value['turn_id'] != node.turn)
            native = value.get('approval_mode') == 'codex'
            if native and node:
                try:
                    created = datetime.fromisoformat(value['created_at'].replace('Z', '+00:00')).timestamp()
                except (KeyError, TypeError, ValueError):
                    created = 0
                stale = stale or (node.last_event > created and node.status != 'permission')
            response = folder/(request_id+'.response.json')
            if expired or stale or not native and not pid_alive(value.get('hook_pid')):
                path.unlink(missing_ok=True)
                response.unlink(missing_ok=True)
                continue
            if not response.exists():
                pending.setdefault(actor, []).append(value)
        self.permission_actors = set(pending)
        node = self.store.nodes.get(self.focused_child) or self.store.nodes.get(self.store.selected)
        candidates = ([node.id] if node else [])+[child.id for child in self.store.children(self.store.selected, self.wall)]
        if self.permission:
            actor = self.permission.get('agent_id') or self.permission.get('session_id')
            if actor in candidates:
                candidates = [actor]+[candidate for candidate in candidates if candidate != actor]
        request = next((min(pending[actor], key=lambda p: p.get('created_at', '')) for actor in candidates if actor in pending), None)
        old = self.permission.get('request_id') if self.permission else None
        if old != (request.get('request_id') if request else None):
            self.permission_page = 0
            self.permission_epoch = self.now
            self.fit_next_frame = True
        self.permission = request

    def leisure_block_reason(self):
        if self.permission or self.permission_actors:
            return '等待审批'
        if self.store.work_tokens():
            return '任务进行中'
        selected = self.store.nodes.get(self.store.selected)
        if selected and selected.active:
            return 'Codex 已暂停' if self.store.paused(selected) else '任务进行中'
        if selected and self.store.visual(selected, self.wall) == 'jump' and self.clock.position(selected.id, self.now):
            return '完成庆祝中'
        if self.transient or self.dragging or self.transition:
            return '动画播放中'
        return ''

    def resolve_visual(self):
        if self.dragging:
            self.position = 'left', self.animations['left'].frame(self.now-self.visual_epoch)
            return
        if self.transient:
            key, once = self.transient
            clip = self.animations[key]
            if not once or self.now-self.visual_epoch < clip.total_duration/1000:
                self.position = key, clip.frame(self.now-self.visual_epoch, once)
                return
            self.transient = None
        if self.permission:
            self.leisure.cancel()
            self.position = 'question', self.animations['question'].frame(self.now-self.permission_epoch, True)
            return
        selected = self.store.nodes.get(self.store.selected)
        position = self.clock.position(selected.id, self.now) if selected else None
        if self.leisure_block_reason():
            self.leisure.cancel()
        else:
            self.leisure.tick(self.now, not self.mouse_down and not self.hidden_edge)
            position = self.leisure.position(self.animations, self.now)
        self.position = position or ('idle', self.animations['idle'].frame(self.now-self.idle_epoch))

    def tick(self):
        self.now, self.wall = time.monotonic(), time.time()
        if self.now-self.last_poll >= .2:
            self.last_poll = self.now
            self.poll()
        self.poll_updates()
        self.advance_transition()
        self.resolve_visual()
        self.update_hover()
        children = tuple((n.id, self.clock.position(n.id, self.now)) for n in self.store.children(self.store.selected, self.wall)[:3])
        decoration = int(self.now*25) if self.position[0] in {'jump', 'sleep_body'} or self.notice and self.notice.release else 0
        signature = self.position, children, self.drag_direction, decoration
        if not self.hidden and (self.dirty or signature != self.last_signature):
            self.last_signature, self.dirty = signature, False
            image = self.renderer.compose(self)
            self.last_pil, self.image = image, qimage(image)
            self.resize(image.width, image.height)
            if self.fit_next_frame and not self.dragging and not self.hidden_edge:
                self.fit_next_frame = False
                self.fit_visible()
            self.place()
            self.input_shape.apply(self, image)
            self.update()
            self.frames_rendered += 1
        elif not self.hidden:
            self.place()
        self.heartbeat()

    def origin(self):
        offset = self.renderer.offset
        return self.anchor-QPoint(round(410+offset[0]), round(570+offset[1]))

    def place(self):
        origin = self.origin()
        if self.pos() != origin:
            self.move(origin)

    def visible_global(self):
        rect = self.renderer.pet_bounds
        return translate(rect, self.anchor.x()-410, self.anchor.y()-570)

    def fit_visible(self):
        bounds = self.last_pil.getbbox() if self.last_pil else None
        if not bounds:
            return
        origin = self.origin()
        rect = translate(bounds, origin.x(), origin.y())
        screen = max(self.screens(), key=lambda s: intersection(rect, s.work))
        dx, dy = fit_delta(rect, screen.work)
        self.anchor += QPoint(round(dx), round(dy))

    def hide_at_edge(self):
        rect = self.visible_global()
        screens = self.screens()
        screen = max(screens, key=lambda s: intersection(rect, s.frame))
        edge = touched_edge(rect, screen, screens)
        if not edge:
            return False
        self.home_anchor = QPoint(self.anchor)
        self.hidden_edge, self.hidden_screen = edge, screen
        self.hidden_since = self.wall
        self.hidden_tokens = self.store.work_tokens().copy()
        node = self.store.nodes.get(self.store.selected)
        self.hidden_family = node.id if node and (node.active or any(c.active for c in self.store.children(node.id, self.wall))) else ''
        left, top, right, bottom = screen.frame
        delta = {'left': (left-rect[2]-16, 0), 'right': (right-rect[0]+16, 0),
                 'top': (0, top-rect[3]-16), 'bottom': (0, bottom-rect[1]+16)}[edge]
        self.transition = ('hide', QPoint(self.anchor), self.anchor+QPoint(*map(round, delta)), self.now)
        self.selector_visible = False
        self.leisure.cancel()
        self.dirty = True
        return True

    def reveal(self, completed=False):
        if not self.hidden_edge or self.transition and self.transition[0] == 'reveal':
            return
        actor = self.hidden_family if completed else ''
        self.reveal_completion = actor
        self.hidden_family = ''
        self.hidden = False
        self.tail.hide()
        self.show()
        self.transient = ('edge_reveal', True)
        self.visual_epoch = self.now
        self.transition = ('reveal', QPoint(self.anchor), QPoint(self.home_anchor), self.now)
        self.dirty = True

    def advance_transition(self):
        if not self.transition:
            return
        action, start, end, began = self.transition
        t = min(1, max(0, (self.now-began)/.48))
        eased = 1-(1-t)**3
        self.anchor = start+QPoint(round((end.x()-start.x())*eased), round((end.y()-start.y())*eased))
        if t < 1:
            return
        self.transition = None
        if action == 'hide':
            self.hidden = True
            self.hide()
            self.tail.refresh()
        else:
            actor = self.reveal_completion
            self.reveal_completion = self.hidden_edge = ''
            if actor and actor in self.store.nodes and not self.store.nodes[actor].active:
                self.celebration_family, self.celebration_started = actor, self.now
                node = self.store.nodes[actor]
                self.clock.tracks.pop(actor, None)
                self.clock.update(actor, node.turn, 'jump', self.now)
                self.store.select(actor)
                self.transient = None
            self.fit_next_frame = self.dirty = True
            self.save_timer.start(250)

    def local_point(self, position):
        return position.x()-self.renderer.offset[0], position.y()-self.renderer.offset[1]

    def update_hover(self):
        old = self.selector_visible
        if self.preview_task:
            self.selector_visible = True
        elif self.permission or self.notice or self.hidden_edge or self.dragging:
            self.selector_visible = False
        else:
            point = self.local_point(self.mapFromGlobal(QCursor.pos()))
            body, panel = self.renderer.pet_bounds, self.renderer.selector_rect
            hit = inside(point, body) or self.selector_visible and inside(point, panel)
            if self.selector_visible and panel:
                corridor = min(body[0], panel[0]), panel[3]-4, max(body[2], panel[2]), body[1]+12
                hit = hit or inside(point, corridor)
            if hit:
                self.selector_visible, self.last_hover = True, self.now
            elif self.now-self.last_hover >= .4:
                self.selector_visible = False
        if old != self.selector_visible:
            self.dirty = True

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.drawImage(0, 0, self.image)

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton or self.transition:
            return
        point = self.local_point(event.position())
        self.click_action = None
        for action, rect in self.renderer.buttons.items():
            if inside(point, rect):
                self.click_action = ('permission', action)
        for action, rect in self.renderer.update_buttons.items():
            if inside(point, rect):
                self.click_action = ('update', action)
        for rect, actor in self.renderer.rows:
            if inside(point, rect):
                self.click_action = ('thread', actor)
        for actor, rect in self.renderer.child_rects.items():
            if inside(point, rect) and actor in self.permission_actors:
                self.focused_child = actor
                self.sync_permissions()
                self.dirty = True
                return
        if self.click_action or inside(point, self.renderer.permission_rect) or inside(point, self.renderer.update_rect):
            return
        self.mouse_down = True
        self.drag_start, self.drag_anchor = event.globalPosition().toPoint(), QPoint(self.anchor)

    def mouseMoveEvent(self, event):
        if not self.mouse_down:
            return
        delta = event.globalPosition().toPoint()-self.drag_start
        if not self.dragging and delta.manhattanLength() > 5:
            self.dragging = True
            self.visual_epoch = self.now
            if self.leisure.phase == 'sleeping':
                self.leisure.reset(self.now)
            else:
                self.leisure.cancel()
        if self.dragging:
            proposed = self.drag_anchor+delta
            if abs(proposed.x()-self.anchor.x()) >= 2:
                self.drag_direction = 1 if proposed.x() > self.anchor.x() else -1
            self.anchor = proposed
            self.dirty = True
            self.place()

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        point = self.local_point(event.position())
        action, self.click_action = self.click_action, None
        if action:
            kind, value = action
            if kind == 'permission' and inside(point, self.renderer.buttons.get(value)):
                self.permission_decision(value)
            elif kind == 'update' and inside(point, self.renderer.update_buttons.get(value)):
                self.update_action(value)
            elif kind == 'thread' and any(actor == value and inside(point, rect) for rect, actor in self.renderer.rows):
                self.open_thread(value)
            return
        if not self.mouse_down:
            return
        self.mouse_down = False
        if self.dragging:
            self.dragging = False
            self.transient = None
            if not self.hide_at_edge():
                self.fit_next_frame = True
                self.save_timer.start(250)
        elif not self.leisure.click(self.now) and not self.store.work_tokens() and not self.permission:
            self.leisure.cancel()
            self.transient, self.visual_epoch = ('flat', True), self.now
        self.dirty = True

    def wheelEvent(self, event):
        point = self.local_point(event.position())
        direction = -1 if event.angleDelta().y() > 0 else 1
        if self.permission and inside(point, self.renderer.permission_rect):
            self.permission_page = max(0, self.permission_page+direction*3)
        elif self.selector_visible:
            self.selector_scroll = max(0, self.selector_scroll+direction)
        self.dirty = True

    def permission_decision(self, decision):
        if not self.permission:
            return
        request_id = self.permission['request_id']
        if self.permission.get('approval_mode') == 'codex':
            if decision == 'open':
                actor = self.permission.get('agent_id') or self.permission.get('session_id')
                self.open_thread(actor)
            if decision in {'open', 'dismiss'}:
                (self.directory/'permission-requests'/(request_id+'.request.json')).unlink(missing_ok=True)
                self.permission = None
                self.dirty = True
            return
        if decision not in {'allow', 'deny'}:
            return
        if decision == 'allow' and request_id not in self.permission_viewed:
            return
        atomic_json(self.directory/'permission-requests'/(request_id+'.response.json'),
                    {'request_id': request_id, 'decision': decision, 'updated_at': utc_now(), 'source': 'googlepiggy-linux'})
        self.permission = None
        self.dirty = True

    def open_thread(self, actor):
        self.store.select(actor)
        self.focused_child = ''
        if self.open_url('codex://threads/'+actor):
            self.store.nodes[actor].unread = False
            self.observer.opened.add(actor)
        else:
            QMessageBox.information(self, 'GooglePiggy', '无法打开 Codex 聊天，请复制聊天 ID：\n'+actor)
        self.dirty = True

    @staticmethod
    def open_url(url):
        if not getattr(sys, 'frozen', False):
            return QDesktopServices.openUrl(QUrl(url))
        # External applications must not inherit PyInstaller's bundled Qt/library paths.
        env = dict(os.environ)
        original = env.pop('LD_LIBRARY_PATH_ORIG', None)
        if original is None:
            env.pop('LD_LIBRARY_PATH', None)
        else:
            env['LD_LIBRARY_PATH'] = original
        for key in ('QT_PLUGIN_PATH', 'QT_QPA_PLATFORM_PLUGIN_PATH', 'PYTHONHOME'):
            env.pop(key, None)
        try:
            return subprocess.run(['xdg-open', url], env=env, timeout=5).returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            return False

    def contextMenuEvent(self, event):
        self.menu(event.globalPos())

    def menu(self, position):
        menu = QMenu()
        responsive = menu.addAction('状态互动（Codex）')
        resting = self.leisure.phase in {'entering', 'sleeping'}
        responsive.setCheckable(True)
        responsive.setChecked(not resting)
        responsive.setEnabled(resting)
        responsive.setToolTip('跟随 Codex 的任务状态；已勾选时无需再次开启。')
        blocked = self.leisure_block_reason()
        rest = menu.addAction('休息模式'+('（'+blocked+'）' if blocked else ''))
        rest.setCheckable(True)
        rest.setChecked(resting)
        rest.setEnabled(not blocked and not resting)
        rest.setToolTip('空闲时立即入睡；新任务到来会自动唤醒。')
        appearance = menu.addAction('外观…')
        approvals = menu.addMenu('审批方式')
        approval_group = QActionGroup(menu)
        approval_group.setExclusive(True)
        approval_choices = {}
        for mode, label in [('pet', '小猪审批（默认）'), ('codex', 'Codex 原生审批，小猪提示跳转')]:
            action = approvals.addAction(label)
            action.setCheckable(True)
            action.setChecked(self.approval_mode == mode)
            approval_group.addAction(action)
            approval_choices[action] = mode
        approvals.setEnabled(not bool(self.permission_actors))
        approvals.setToolTip('先处理当前审批，再切换后续请求的审批方式。')
        update = menu.addAction('正在检查更新…' if self.updater.checking else '检查更新…')
        try:
            auto = autostart_enabled()
            autostart = menu.addAction('关闭开机自启动' if auto else '开启开机自启动')
        except OSError:
            auto = False
            autostart = menu.addAction('自启动状态未确认')
        hooks = menu.addAction('Codex Hook 首次授权说明')
        exit_action = menu.addAction('退出猪猪桌宠')
        chosen = menu.exec(position)
        try:
            if chosen == exit_action:
                self.quit()
            elif chosen == appearance:
                self.show_appearance()
            elif chosen in approval_choices:
                self.set_approval_mode(approval_choices[chosen])
            elif chosen == autostart:
                set_autostart(not auto)
            elif chosen == update:
                self.updater.check(manual=True)
            elif chosen == hooks:
                QMessageBox.information(self, 'GooglePiggy', '在 Codex 设置 → Hooks 或 CLI /hooks 中检查并信任 GooglePiggy Linux。\n桌宠不会修改信任数据库；每项权限请求都由你单独决定。')
            elif chosen == rest and not self.leisure_block_reason():
                self.transient = None
                self.leisure.enter(self.now)
            elif chosen == responsive:
                self.leisure.reset(self.now)
                self.transient = None
        except (OSError, ValueError) as error:
            QMessageBox.warning(self, 'GooglePiggy', str(error))
        self.dirty = True

    def set_approval_mode(self, mode):
        if mode not in {'pet', 'codex'}:
            return
        value = read_json(self.directory/'settings.json')
        value = value if isinstance(value, dict) else {}
        value['approvalMode'] = mode
        atomic_json(self.directory/'settings.json', value)
        self.approval_mode = mode

    def poll_updates(self):
        while True:
            try:
                kind, value, error = self.updater.results.get_nowait()
            except queue.Empty:
                break
            if kind == 'check':
                self.updater.checking = False
                manual, self.updater.manual = self.updater.manual, False
                if manual or value:
                    self.notice = UpdateNotice(value, error)
                    self.fit_next_frame = True
                    if self.hidden_edge and not self.hidden_family:
                        self.reveal()
            elif self.notice:
                if kind == 'progress':
                    self.notice.progress = value
                elif kind == 'ready':
                    self.update_package = value
                    self.notice.phase = 'ready'
                elif kind == 'failed':
                    self.notice.phase, self.notice.error = 'available', error
                else:
                    self.notice.phase = kind
            self.dirty = True
        if self.update_package and not self.permission_actors and not self.dragging and not self.hidden_edge:
            package, self.update_package = self.update_package, None
            self.install_update(package)

    def update_action(self, action):
        if not self.notice:
            return
        if action == 'dismiss':
            self.notice = None
        elif action == 'cancel':
            self.updater.cancel.set()
        elif action == 'update' and self.notice.release:
            if not getattr(sys, 'frozen', False):
                self.notice.error = '源码运行请使用 Git 更新；发行包支持自动备份更新。'
            else:
                self.notice.error, self.notice.phase = None, 'downloading'
                self.updater.download(self.notice.release)
        self.dirty = True

    def install_update(self, package):
        job = self.directory/'update-job.json'
        atomic_json(job, {'target': str(app_root()), 'package': str(package), 'version': self.notice.release.version,
                          'old_pid': os.getpid(), 'state_dir': str(self.directory)})
        try:
            with (self.directory/'update.log').open('a') as log:
                subprocess.Popen([sys.executable, '--apply-update', str(job)], stdout=log, stderr=log, start_new_session=True)
            self.quit()
        except OSError as error:
            self.notice.error, self.notice.phase = str(error), 'available'
            self.dirty = True

    def heartbeat(self, force=False):
        if not force and self.now-self.last_heartbeat < 1:
            return
        self.last_heartbeat = self.now
        value = {'pid': os.getpid(), 'updated_at': utc_now(), 'version': VERSION+'-linux', 'platform': QApplication.platformName(),
                 'current_key': self.position[0], 'frame_index': self.position[1], 'window_visible': self.isVisible(),
                 'window_rect': screen_rect(self.geometry()), 'content_screen_rect': self.visible_global(),
                 'selected_family': self.store.selected, 'families': [{'id': n.id, 'parent': n.parent, 'turn': n.turn,
                 'status': n.status, 'unread': n.unread} for n in self.store.nodes.values()],
                 'presentation': self.transition[0] if self.transition else 'hidden' if self.hidden else 'visible',
                 'hidden_edge': self.hidden_edge, 'tail_visible': self.tail.isVisible(), 'leisure_phase': self.leisure.phase,
                 'appearance': self.appearance.values, 'appearance_preview': {'dialog': self.preview_dialog, 'task': self.preview_task},
                 'permission_request_id': self.permission['request_id'] if self.permission else '', 'frames_rendered': self.frames_rendered,
                 'approval_mode': self.approval_mode,
                 'update_phase': self.notice.phase if self.notice else None, 'unread_sync': self.observer.unread_supported}
        atomic_json(self.directory/'pig-heartbeat.json', value)

    def capture(self, path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.grab().save(str(path))

    def quit(self):
        self.timer.stop()
        self.save_settings()
        self.observer.close()
        self.updater.cancel.set()
        if self.appearance_dialog:
            self.appearance_dialog.close()
        self.tail.close()
        self.input_shape.close()
        self.close()
        QApplication.quit()


def run(args):
    directory = state_dir()
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (directory/'instance.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print('GooglePiggy 已在运行。')
            return
        app = QApplication([])
        app.setApplicationName('GooglePiggy')
        app.setQuitOnLastWindowClosed(False)
        app.setWindowIcon(QIcon(str(resource_root()/'AppIcon-1024.png')))
        for bold in (False, True):
            path = font_file(bold)
            if path:
                QFontDatabase.addApplicationFont(str(path))
        if font_file():
            app.setFont(QFont('Noto Sans CJK SC', 10))
        if app.platformName() == 'wayland':
            raise RuntimeError('首版需要 GNOME/X11；Wayland 不提供桌宠所需的绝对定位。请使用 Ubuntu on Xorg 会话。')
        window = PetWindow(args, directory)
        def report_error(kind, value, traceback):
            import traceback as trace
            with (directory/'pig-pet-error.log').open('a', encoding='utf-8') as log:
                log.write(utc_now()+'\n')
                trace.print_exception(kind, value, traceback, file=log)
            sys.__excepthook__(kind, value, traceback)
            window.quit()
        sys.excepthook = report_error
        app.exec()
        # Keep the window and advisory lock alive through the entire event loop.
        del window

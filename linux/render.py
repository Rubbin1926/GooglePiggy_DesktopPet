"""Pillow presentation matching the upstream 640-point artwork and UI layout."""
import math
from functools import lru_cache
from pathlib import Path
from types import SimpleNamespace

from PIL import Image, ImageDraw, ImageFilter, ImageFont
from appearance import opacity, transforms
from linux.geometry import union
from linux.paths import font_file

SLOTS = [(310, 575), (410, 615), (510, 575)]


@lru_cache(maxsize=32)
def font(size, bold=False):
    for path in (font_file(bold), f'/usr/share/fonts/truetype/dejavu/DejaVuSans{"-Bold" if bold else ""}.ttf'):
        if path is None:
            continue
        if Path(path).is_file():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default(size=size)


def wrap(draw, text, face, width, limit=10000):
    text = ' '.join(str(text).split())
    lines, current = [], ''
    for char in text:
        if current and draw.textlength(current+char, font=face) > width:
            lines.append(current)
            current = ''
            if len(lines) >= limit:
                return lines
        current += char
    return lines+[current] if current else lines


def resize(image, size):
    return image.convert('RGBa').resize(size, Image.Resampling.BILINEAR).convert('RGBA')


@lru_cache(maxsize=16)
def surface(rect, color=None, alpha=1):
    # Same antialiased border, arrow, shadow and gradient as windows_pet.py.
    left, top, right, bottom = rect
    height = bottom-top
    large = Image.new('L', (1920, 1920))
    draw = ImageDraw.Draw(large)
    draw.rounded_rectangle(tuple(v*3 for v in rect), 60, fill=255)
    draw.polygon([(402*3, (bottom-1)*3), (418*3, (bottom-1)*3), (410*3, (bottom+10)*3)], fill=255)
    mask = large.resize((640, 640), Image.Resampling.LANCZOS)
    inside = mask.filter(ImageFilter.MinFilter(5))
    gradient = Image.new('RGBA', (640, 640))
    pixels = gradient.load()
    for y in range(max(0, top), bottom+14):
        for x in range(left, right+1):
            t = min(1, ((x-left)*320+(y-top)*(height+10))/(320**2+(height+10)**2))
            pixels[x, y] = round(253-2*t), round(249-19*t), round(246-11*t), 255
    canvas = Image.new('RGBA', (640, 640))
    shadow = Image.new('RGBA', (640, 640))
    shadow.putalpha(mask.filter(ImageFilter.GaussianBlur(8)).point(lambda v: round(v*.18)))
    canvas.alpha_composite(shadow, (0, 4))
    empty = Image.new('RGBA', (640, 640))
    canvas.alpha_composite(Image.composite(Image.new('RGBA', (640, 640), (231, 169, 188, 255)), empty, mask))
    canvas.alpha_composite(Image.composite(gradient, empty, inside))
    if color:
        canvas.alpha_composite(Image.composite(Image.new('RGBA', (640, 640), color), empty, inside))
    return opacity(canvas, alpha)


class Renderer:
    def __init__(self, resources, clips):
        self.clips = clips
        self.effects = {key: Image.open(resources/'effects'/(key+'.png')).convert('RGBA')
                        for key in ('sparkle', 'firework')}
        self.child_rects, self.rows, self.buttons, self.update_buttons = {}, [], {}, {}
        self.selector_rect = self.permission_rect = self.update_rect = None
        self.pet_bounds = (334, 436, 486, 570)
        self.offset = (0, 0)

    @lru_cache(maxsize=128)
    def child_sprite(self, key, index):
        return resize(self.clips[key].frames[index], (261, 307))

    def effects_on(self, canvas, elapsed):
        if not 0 <= elapsed <= 1.35:
            return
        progress = elapsed/1.35
        fade = min(1, progress/.18)*min(1, (1-progress)/.28)
        def paste(key, x, y, size, alpha):
            if size <= 0 or alpha <= 0:
                return
            source = self.effects[key]
            sprite = source.resize((size, max(1, round(size*source.height/source.width))), Image.Resampling.LANCZOS)
            canvas.alpha_composite(opacity(sprite, alpha), (x-sprite.width//2, y-sprite.height//2))
        paste('firework', 480, 462, round(34+28*min(1, progress/.42)), fade*.82)
        for x, y, size, phase in [(334, 446, 19, 0), (459, 415, 15, .13), (364, 404, 12, .26)]:
            local = (progress-phase)/(1-phase)
            if 0 <= local <= 1:
                pulse = math.sin(math.pi*local)
                paste('sparkle', x, y, round(size*(.6+.55*pulse)), fade*pulse)

    def selector(self, pet, canvas, preview):
        roots = pet.store.roots(pet.wall)
        if preview:
            roots = [SimpleNamespace(id='', title=t, unread=i == 1) for i, t in enumerate(
                ('预览 · 正在整理任务', '预览 · 已完成的对话', '预览 · 等待你的确认'))]
        left, bottom, width = 270, 425, 280
        top = bottom-(max(1, min(6, len(roots)))*34+12)
        self.selector_rect = (left, top, left+width, bottom)
        bg = Image.new('RGBA', canvas.size)
        draw = ImageDraw.Draw(bg)
        draw.rounded_rectangle(self.selector_rect, 12, fill=pet.appearance.color('taskColor', (220, 218, 222, 255)), outline=(245, 242, 245, 255))
        pet.selector_scroll = min(pet.selector_scroll, max(0, len(roots)-6))
        roots = roots[pet.selector_scroll:pet.selector_scroll+6]
        for i, node in enumerate(roots):
            if node.id and node.id == pet.store.selected:
                draw.rounded_rectangle((left+6, top+6+i*34, left+width-6, top+40+i*34), 7, fill=(245, 240, 246, 235))
        canvas.alpha_composite(opacity(bg, pet.appearance.taskOpacity))
        draw = ImageDraw.Draw(canvas)
        self.rows = []
        ink = pet.appearance.color('taskTextColor', (78, 72, 80, 255))
        if not roots:
            draw.text((left+18, top+12), '当前好像没有任务唔～', font=font(14), fill=ink)
        for i, node in enumerate(roots):
            rect = left+6, top+6+i*34, left+width-6, top+40+i*34
            if node.unread:
                draw.ellipse((left+12, rect[1]+13, left+19, rect[1]+20), fill=(47, 137, 229, 255))
            title = node.title
            while title and draw.textlength(title, font=font(14)) > width-48:
                title = title[:-2]+'…'
            draw.text((left+28, rect[1]+7), title, font=font(14), fill=ink)
            if not preview:
                self.rows.append((rect, node.id))

    def permission(self, pet, canvas, preview):
        request = {'summary': '这是外观预览。你可以调整对话框大小、颜色、距离与不透明度。'} if preview else pet.permission
        detail = str(request.get('summary') or 'Codex 请求权限')
        native = not preview and request.get('approval_mode') == 'codex'
        lines = self.permission_lines(detail)
        pet.permission_page = min(pet.permission_page, max(0, len(lines)-11))
        visible = lines[pet.permission_page:pet.permission_page+11]
        left, right, bottom = 250, 570, 348
        top = bottom-(104+max(1, len(visible))*20)
        rect = left, top, right, bottom
        self.permission_rect = left, top, right, bottom+10
        canvas.alpha_composite(surface(rect, pet.appearance.dialogColor, pet.appearance.dialogOpacity))
        draw = ImageDraw.Draw(canvas)
        rose = (176, 124, 129, 255)
        draw.ellipse((left+20, top+21, left+26, top+27), fill=rose)
        title = '外观预览 · 示例对话框' if preview else 'CODEX · 请在 Codex 中确认' if native else 'CODEX · 需要你的确认'
        draw.text((left+34, top+17), title,
                  font=font(11), fill=pet.appearance.color('dialogTextColor', rose))
        for i, line in enumerate(visible):
            draw.text((left+20, top+43+i*20), line, font=font(14), fill=pet.appearance.color('dialogTextColor', (76, 67, 70, 255)))
        if not preview and pet.permission_page+11 >= len(lines):
            pet.permission_viewed.add(request['request_id'])
        self.buttons = {('dismiss' if native else 'deny'): (left+20, bottom-48, left+120, bottom-16),
                        ('open' if native else 'allow'): (right-136, bottom-48, right-20, bottom-16)}
        for action, button in self.buttons.items():
            disabled = not preview and action == 'allow' and request['request_id'] not in pet.permission_viewed
            primary = action in {'allow', 'open'}
            fill = (223, 207, 214, 255) if disabled else rose if primary else (242, 238, 231, 255)
            layer = Image.new('RGBA', canvas.size)
            ImageDraw.Draw(layer).rounded_rectangle(button, 10, fill=fill)
            canvas.alpha_composite(opacity(layer, pet.appearance.buttonOpacity))
            draw = ImageDraw.Draw(canvas)
            label = {'allow': '允许一次', 'deny': '拒绝', 'open': '前往 Codex', 'dismiss': '关闭提示'}[action]
            draw.text(((button[0]+button[2])/2, (button[1]+button[3])/2), label,
                      font=font(13), anchor='mm', fill=pet.appearance.color('buttonTextColor',
                      (255, 255, 255, 255) if primary and not disabled else (82, 76, 76, 255)))
        if preview:
            self.buttons = {}

    @lru_cache(maxsize=8)
    def permission_lines(self, detail):
        return wrap(ImageDraw.Draw(Image.new('RGBA', (1, 1))), detail, font(14), 280)

    def compose(self, pet):
        now, wall = pet.now, pet.wall
        key, index = pet.position
        canvas = self.clips[key].frames[index].copy()
        if key == 'left' and pet.dragging and pet.drag_direction > 0:
            mirrored = canvas.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
            canvas = Image.new('RGBA', (640, 640))
            canvas.alpha_composite(mirrored, (180, 0))
        if key == 'sleep_body':
            elapsed = now-pet.leisure.tail_epoch if pet.leisure.tail_epoch is not None else 2
            tail = self.clips['sleep_tail'].frame(elapsed, True) if elapsed < 1.44 else 0
            canvas.alpha_composite(self.clips['sleep_tail'].frames[tail])
            canvas.alpha_composite(self.clips['sleep_z'].frames[self.clips['sleep_z'].frame(now-pet.leisure.sleep_epoch)])
        if key == 'jump':
            node = pet.store.nodes.get(pet.store.selected)
            elapsed = now-pet.celebration_started if pet.celebration_family == pet.store.selected else wall-node.completion if node and node.completion else now-pet.visual_epoch
            self.effects_on(canvas, elapsed)
        children = pet.store.children(pet.store.selected, wall)
        self.child_rects = {}
        for i, node in enumerate(children[:3]):
            point = tuple(a+.14*(b-a) for a, b in zip(pet.child_positions.get(node.id, SLOTS[i]), SLOTS[i]))
            pet.child_positions[node.id] = point
            pos = ('left', self.clips['left'].frame(now-pet.visual_epoch)) if pet.dragging else pet.clock.position(node.id, now)
            if not pos:
                continue
            child_key, child_index = pos
            if child_key == 'carrot':
                child_index = self.clips['carrot'].frame(max(0, wall-node.changed)*1.25)
            sprite = self.child_sprite(child_key, child_index)
            mirror = pet.dragging and (int((now-pet.visual_epoch)/.6)+i) % 2
            if mirror:
                sprite = sprite.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
            anchor_x = 261-410*.408 if mirror else 410*.408
            origin = round(point[0]-anchor_x), round(point[1]-570*.48)
            canvas.alpha_composite(sprite, origin)
            bounds = sprite.getbbox()
            if bounds:
                self.child_rects[node.id] = tuple(bounds[j]+origin[j % 2] for j in range(4))
        if len(children) > 3:
            ImageDraw.Draw(canvas).text((540, 570), '+'+str(len(children)-3), font=font(16, True), fill=(96, 84, 88, 255))
        pet_t, dialog_t, task_t = transforms(pet.appearance)
        self.pet_bounds = pet_t.rect(canvas.getbbox() or (334, 436, 486, 570))
        self.child_rects = {actor: pet_t.rect(rect) for actor, rect in self.child_rects.items()}
        if pet.notice and not pet.permission:
            pet.notice.draw_decoration(canvas)
        layers = [(canvas, pet_t)]
        self.selector_rect, self.rows = None, []
        if pet.selector_visible or pet.preview_task:
            layer = Image.new('RGBA', (640, 640))
            self.selector(pet, layer, pet.preview_task)
            self.selector_rect = task_t.rect(self.selector_rect)
            self.rows = [(task_t.rect(rect), actor) for rect, actor in self.rows]
            layers.append((layer, task_t))
        self.permission_rect, self.buttons = None, {}
        self.update_rect, self.update_buttons = None, {}
        if pet.permission or pet.preview_dialog:
            layer = Image.new('RGBA', (640, 640))
            self.permission(pet, layer, not pet.permission)
            self.permission_rect = dialog_t.rect(self.permission_rect)
            self.buttons = {action: dialog_t.rect(rect) for action, rect in self.buttons.items()}
            layers.append((layer, dialog_t))
        elif pet.notice:
            layer = Image.new('RGBA', (640, 640))
            pet.notice.draw(layer, pet.version, font,
                            lambda rect: surface(rect, pet.appearance.dialogColor, pet.appearance.dialogOpacity),
                            wrap, appearance=pet.appearance, decoration=False)
            self.update_rect = dialog_t.rect(pet.notice.rect)
            self.update_buttons = {action: dialog_t.rect(rect) for action, rect in pet.notice.buttons.items()}
            layers.append((layer, dialog_t))
        # Reserve a stable pet canvas; UI may extend it without moving the body anchor.
        bounds = [pet_t.rect((200, 200, 640, 640))]
        bounds.extend(transform.rect(layer.getbbox()) for layer, transform in layers if layer.getbbox())
        extent = union(bounds)
        extent = tuple(math.floor((v-4)/4)*4 if i < 2 else math.ceil((v+4)/4)*4 for i, v in enumerate(extent))
        self.offset = -extent[0], -extent[1]
        result = Image.new('RGBA', (extent[2]-extent[0], extent[3]-extent[1]))
        for layer, transform in layers:
            transform.paste(result, layer, self.offset)
        return result

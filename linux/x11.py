"""X11 input masks for Ubuntu LTS; keep antialiased artwork unclipped."""
import ctypes
import ctypes.util
import numpy as np


class Rectangle(ctypes.Structure):
    _fields_ = [('x', ctypes.c_short), ('y', ctypes.c_short),
                ('width', ctypes.c_ushort), ('height', ctypes.c_ushort)]


def alpha_rectangles(image):
    mask = np.asarray(image.getchannel('A')) > 12
    changes = np.diff(np.pad(mask.astype(np.int8), ((0, 0), (1, 1))), axis=1)
    active, result = {}, []
    for y, row in enumerate(changes):
        starts, ends = np.flatnonzero(row == 1), np.flatnonzero(row == -1)
        current = {}
        for start, end in zip(starts, ends):
            key = int(start), int(end-start)
            rect = active.pop(key, [key[0], y, key[1], 0])
            rect[3] += 1
            current[key] = rect
        result.extend(active.values())
        active = current
    result.extend(active.values())
    return result


class InputShape:
    def __init__(self, enabled):
        self.display = None
        if not enabled:
            return
        self.xlib = ctypes.CDLL(ctypes.util.find_library('X11'))
        self.shape = ctypes.CDLL(ctypes.util.find_library('Xext'))
        self.xlib.XOpenDisplay.argtypes = [ctypes.c_char_p]
        self.xlib.XOpenDisplay.restype = ctypes.c_void_p
        self.xlib.XFlush.argtypes = [ctypes.c_void_p]
        self.xlib.XCloseDisplay.argtypes = [ctypes.c_void_p]
        self.shape.XShapeCombineRectangles.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_int,
            ctypes.c_int, ctypes.c_int, ctypes.POINTER(Rectangle), ctypes.c_int, ctypes.c_int, ctypes.c_int]
        self.display = self.xlib.XOpenDisplay(None)
        if not self.display:
            raise RuntimeError('无法连接 X11 显示服务器')

    def apply(self, widget, image):
        if not self.display:
            return
        dpr = widget.devicePixelRatioF()
        if dpr != 1:
            image = image.resize((round(image.width*dpr), round(image.height*dpr)))
        rects = alpha_rectangles(image)
        values = (Rectangle*len(rects))(*(Rectangle(*rect) for rect in rects))
        self.shape.XShapeCombineRectangles(self.display, int(widget.winId()), 2, 0, 0, values, len(rects), 0, 0)
        self.xlib.XFlush(self.display)

    def close(self):
        if self.display:
            self.xlib.XCloseDisplay(self.display)
            self.display = None

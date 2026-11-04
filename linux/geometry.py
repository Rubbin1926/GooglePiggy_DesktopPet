"""Pure screen geometry in Qt logical coordinates (including negative origins)."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Screen:
    frame: tuple
    work: tuple


def union(rects):
    return (min(r[0] for r in rects), min(r[1] for r in rects),
            max(r[2] for r in rects), max(r[3] for r in rects))


def inside(point, rect):
    return rect is not None and rect[0] <= point[0] < rect[2] and rect[1] <= point[1] < rect[3]


def translate(rect, dx, dy):
    return tuple(value + (dx if i % 2 == 0 else dy) for i, value in enumerate(rect))


def intersection(a, b):
    return max(0, min(a[2], b[2])-max(a[0], b[0])) * max(0, min(a[3], b[3])-max(a[1], b[1]))


def fit_delta(rect, work, margin=8):
    """Keep the visible artwork in the work area, rather than its empty canvas."""
    dx = max(work[0]+margin-rect[0], min(0, work[2]-margin-rect[2]))
    dy = max(work[1]+margin-rect[1], min(0, work[3]-margin-rect[3]))
    return dx, dy


def touched_edge(rect, screen, screens, tolerance=10):
    left, top, right, bottom = screen.frame
    x, y = (rect[0]+rect[2])/2, (rect[1]+rect[3])/2
    probes = [('left', rect[0]-left, (left-1, y)),
              ('right', right-rect[2], (right+1, y)),
              ('top', rect[1]-top, (x, top-1)),
              ('bottom', bottom-rect[3], (x, bottom+1))]
    candidates = [(abs(distance), edge) for edge, distance, probe in probes
                  if distance <= tolerance and not any(inside(probe, other.frame) for other in screens if other != screen)]
    return min(candidates)[1] if candidates else None


def tail_rects(edge, screen, anchor, count, scale=1):
    """Keep the exposed tail group in the usable area, clear of GNOME panels."""
    left, top, right, bottom = screen.work
    size, child, gap = round(68*scale), round(32*scale), round(4*scale)
    vertical = edge in ('left', 'right')
    low, high = (top, bottom) if vertical else (left, right)
    extent = size + count*(child+gap)
    start = max(low+4, min(anchor[1] if vertical else anchor[0], high-extent-4))
    result = []
    for i in range(count+1):
        side = size if i == 0 else child
        along = start if i == 0 else start+size+gap+(i-1)*(child+gap)
        visible = round((30 if i == 0 else 14)*scale)
        if edge == 'left':
            rect = left-(side-visible), along, left+visible, along+side
        elif edge == 'right':
            rect = right-visible, along, right+(side-visible), along+side
        elif edge == 'top':
            rect = along, top-(side-visible), along+side, top+visible
        else:
            rect = along, bottom-visible, along+side, bottom+(side-visible)
        result.append(rect)
    return result

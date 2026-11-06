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


def tail_safe_screen(screen, dock, primary=True):
    """Reserve overlay space for an auto-hiding Dock without shrinking pet movement."""
    if not dock:
        return screen
    edge, size, multiple, fixed = dock
    if fixed or not primary and not multiple:
        return screen
    work = list(screen.work)
    size = min(size, (work[2]-work[0] if edge in ('left','right') else work[3]-work[1])//3)
    if edge == 'left': work[0] += size
    elif edge == 'right': work[2] -= size
    elif edge == 'top': work[1] += size
    else: work[3] -= size
    return Screen(screen.frame, tuple(work))


def tail_rects(edge, screen, anchor, count, scale=1):
    """Fully visible, comfortably clickable tail targets inside the usable area."""
    left, top, right, bottom = screen.work
    shortest = min(right-left, bottom-top)
    inset = min(max(12, min(24, round(shortest*.02))), max(0, (shortest-1)//4))
    vertical = edge in ('left', 'right')
    low, high = (top, bottom) if vertical else (left, right)
    available = high-low-2*inset
    limit = max(1, min(available, (right-left if vertical else bottom-top)-2*inset))
    size, child = min(limit, max(48, round(68*scale))), min(limit, max(48, round(32*scale)))
    gap = max(6, round(4*scale))
    while count and size+count*(child+gap) > available:
        count -= 1
    extent = size + count*(child+gap)
    start = max(low+inset, min(round((anchor[1] if vertical else anchor[0])-size/2), high-extent-inset))
    result = []
    for i in range(count+1):
        side = size if i == 0 else child
        along = start if i == 0 else start+size+gap+(i-1)*(child+gap)
        if edge == 'left':
            rect = left+inset, along, left+inset+side, along+side
        elif edge == 'right':
            rect = right-inset-side, along, right-inset, along+side
        elif edge == 'top':
            rect = along, top+inset, along+side, top+inset+side
        else:
            rect = along, bottom-inset-side, along+side, bottom-inset
        result.append(rect)
    return result

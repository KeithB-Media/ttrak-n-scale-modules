"""
Nest every laser-cut part of the Portal North Bridge 6-module set onto 600 x 3000 mm sheets.

The 618 mm long parts are longer than the 600 mm bed width, so they run along the 3000 mm
direction.  Every part needed for the whole set is placed (no "cut N times"):
    4 x lowered box  (3 arch modules + 1 viaduct module)
    2 x transition   (west + east; the east one is assembled as a mirror image)
Each part gets a small engraved tag (B1..B4 = lowered boxes, T1/T2 = transitions) so the
sets stay sorted after cutting.

Output (both module heights are kept):
    ttrak_output/portal_bridge/laser/<height>/sheets_600x3000/portal_set_sheet_<n>_of_<m>.svg
Run:  python portal_nest.py
"""

import os
import portal_laser as pl

SHEET_W, SHEET_H = 3000.0, 600.0      # bed size (x = 3000 long direction, y = 600)
MARGIN = 6.0                          # keep clear of the sheet edge
GAP = 4.0                             # between parts


# ----------------------------------------------------------------------------
# MaxRects bin packing (best-short-side-fit, 90 degree rotation allowed)
# ----------------------------------------------------------------------------
class MaxRects:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.free = [(0.0, 0.0, w, h)]          # x, y, w, h

    def insert(self, w, h):
        best = None
        for fx, fy, fw, fh in self.free:
            for rw, rh, rot in ((w, h, False), (h, w, True)):
                if rw <= fw + 1e-9 and rh <= fh + 1e-9:
                    short = min(fw - rw, fh - rh)
                    long_ = max(fw - rw, fh - rh)
                    key = (short, long_, fx, fy)
                    if best is None or key < best[0]:
                        best = (key, fx, fy, rw, rh, rot)
        if best is None:
            return None
        _, x, y, rw, rh, rot = best
        self._split(x, y, rw, rh)
        return x, y, rot

    def _split(self, x, y, w, h):
        new = []
        for fx, fy, fw, fh in self.free:
            if x >= fx + fw or x + w <= fx or y >= fy + fh or y + h <= fy:
                new.append((fx, fy, fw, fh))
                continue
            if x > fx:
                new.append((fx, fy, x - fx, fh))
            if x + w < fx + fw:
                new.append((x + w, fy, fx + fw - x - w, fh))
            if y > fy:
                new.append((fx, fy, fw, y - fy))
            if y + h < fy + fh:
                new.append((fx, y + h, fw, fy + fh - y - h))
        # prune rectangles contained in others
        pruned = []
        for i, a in enumerate(new):
            if any(j != i and a[0] >= b[0] - 1e-9 and a[1] >= b[1] - 1e-9 and
                   a[0] + a[2] <= b[0] + b[2] + 1e-9 and a[1] + a[3] <= b[1] + b[3] + 1e-9
                   and (a != b or j < i) for j, b in enumerate(new)):
                continue
            pruned.append(a)
        self.free = pruned


def part_list():
    parts = []
    for i in range(4):
        parts += [("B%d" % (i + 1), p) for p in pl.arch_module()]
    for i in range(2):
        parts += [("T%d" % (i + 1), p) for p in pl.transition_module()]
    return parts


def pack(parts):
    """Largest first; open a new sheet whenever a part does not fit."""
    order = sorted(parts, key=lambda tp: -(tp[1].bbox()[2] - tp[1].bbox()[0]) * (tp[1].bbox()[3] - tp[1].bbox()[1]))
    sheets = []                     # [(MaxRects, [(tag, panel, x, y, rot)])]
    uw, uh = SHEET_W - 2 * MARGIN, SHEET_H - 2 * MARGIN
    for tag, p in order:
        u0, v0, u1, v1 = p.bbox()
        w, h = u1 - u0 + GAP, v1 - v0 + GAP
        for mr, placed in sheets:
            r = mr.insert(w, h)
            if r:
                placed.append((tag, p) + r)
                break
        else:
            mr = MaxRects(uw + GAP, uh + GAP)
            r = mr.insert(w, h)
            if r is None:
                raise ValueError("%s (%.0f x %.0f) does not fit the sheet" % (p.name, w, h))
            sheets.append((mr, [(tag, p) + r]))
    return [placed for _, placed in sheets]


# ----------------------------------------------------------------------------
# SVG
# ----------------------------------------------------------------------------
def xf(p, x, y, rot):
    """Local (u,v) -> sheet coords. Not rotated: u right, v up (SVG y down).
    Rotated 90 degrees: u runs down the sheet, v runs right."""
    u0, v0, u1, v1 = p.bbox()

    def f(pt):
        u, v = pt[0] - u0, pt[1] - v0
        if not rot:
            return MARGIN + x + u, MARGIN + y + (v1 - v0) - v
        return MARGIN + x + v, MARGIN + y + u
    return f


def d_of(pts, close=True):
    return "M" + " L".join("%.3f,%.3f" % q for q in pts) + (" Z" if close else "")


def write_sheet(path, placed, n, m, label):
    cut, inner, eng = [], [], []
    sw = 0.1
    for tag, p, x, y, rot in placed:
        f = xf(p, x, y, rot)
        cut.append('<path id="%s_%s" d="%s" stroke="%s" stroke-width="%s" fill="none"/>'
                   % (tag, p.name, d_of([f(q) for q in p.outline]), pl.PURPLE, sw))
        for h in p.holes:
            inner.append('<path d="%s" stroke="%s" stroke-width="%s" fill="none"/>'
                         % (d_of([f(q) for q in h]), pl.GREEN, sw))
        for e in p.engrave:
            eng.append('<path d="%s" stroke="%s" stroke-width="%s" fill="none"/>'
                       % (d_of([f(q) for q in e], close=len(e) > 2), pl.RED, sw))
        # one tag per part: set id + part name, placed at the part's centre
        u0, v0, u1, v1 = p.bbox()
        cx, cy = f(((u0 + u1) / 2, (v0 + v1) / 2))
        size = 4.0 if min(u1 - u0, v1 - v0) > 30 else 3.0
        text = "%s %s" % (tag, p.name.replace("_", " "))
        rot_attr = ' transform="rotate(90 %.2f %.2f)"' % (cx, cy) if rot else ""
        eng.append('<text x="%.2f" y="%.2f" font-family="Arial, sans-serif" font-size="%.1f" '
                   'text-anchor="middle" fill="%s"%s>%s</text>' % (cx, cy, size, pl.RED, rot_attr, text))
    note = ("Portal North Bridge 6-module set - %s - sheet %d of %d - 600 x 3000 mm - 5mm ply. "
            "Purple: cut, kerf OUT. Green: inside cut, kerf IN. Red: engrave or delete. "
            "B1-B4 = lowered boxes (3 arch + 1 viaduct), T1-T2 = transitions (T2 assembled mirrored)."
            % (label, n, m))
    eng.append('<text x="%.2f" y="%.2f" font-family="Arial, sans-serif" font-size="4" fill="%s">%s</text>'
               % (MARGIN, SHEET_H - 1.5, pl.RED, note))
    svg = ['<?xml version="1.0" encoding="utf-8"?>',
           '<svg version="1.1" xmlns="http://www.w3.org/2000/svg" width="%gmm" height="%gmm" viewBox="0 0 %g %g">'
           % (SHEET_W, SHEET_H, SHEET_W, SHEET_H),
           '<g id="Cut_Outside_Purple">' + "".join(cut) + "</g>",
           '<g id="Cut_Inside_Green">' + "".join(inner) + "</g>",
           '<g id="Engrave_Red">' + "".join(eng) + "</g>",
           "</svg>"]
    with open(path, "w") as fh:
        fh.write("\n".join(svg))


def run():
    base = pl.out_dir()
    report = []
    for label, top in (("70mm_template", 70.09), ("63.5mm_2.5in", 63.5)):
        pl.TOP = top
        sheets = pack(part_list())
        d = os.path.join(base, label, "sheets_600x3000")
        os.makedirs(d, exist_ok=True)
        for f in os.listdir(d):
            if f.endswith(".svg"):
                os.remove(os.path.join(d, f))
        for i, placed in enumerate(sheets):
            write_sheet(os.path.join(d, "portal_set_sheet_%d_of_%d_%s.svg" % (i + 1, len(sheets), label)),
                        placed, i + 1, len(sheets), "module height %.2f mm" % top)
        report.append((label, len(sheets), [len(s) for s in sheets], d))
    pl.TOP = 70.09
    return report


if __name__ == "__main__":
    for label, n, counts, d in run():
        print("%s: %d sheets, parts per sheet %s -> %s" % (label, n, counts, d))

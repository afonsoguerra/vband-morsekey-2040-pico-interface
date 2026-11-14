#!/usr/bin/env python3
"""Generate DXFs for wooden Choc V2 keycaps with a hidden aluminium stem insert.

Outputs (mm, origin bottom-left):
  caps_wood_6mm.dxf        8 plywood caps: insert pocket + outline
  inserts_alu_3mm.dxf      8 aluminium inserts: through cross socket + outline
  test_strip_alu_3mm.dxf   cross-socket fit test (6 sizes x 2 orientations)

Usage:  python3 make_dxf.py [--offset 0.03]
  --offset  added to both cross slot widths of the inserts (pick from test strip)
Needs:  pip install ezdxf  (matplotlib optional, for preview.png)
"""
import argparse
import math
from pathlib import Path

import ezdxf

# ---- parameters (mm) -------------------------------------------------------
N_CAPS = 8
COLS = 4

CAP_W, CAP_H, CAP_R = 17.5, 16.5, 1.5   # Choc spacing is 18 x 17
CAP_GAP = 8.0                           # space between caps (>= tool dia + margin)

INS_W, INS_H, INS_R = 9.0, 8.0, 1.6     # rectangle = only fits one way (keeps cross orientation)
INS_GAP = 6.0
POCKET_CLEAR = 0.05                     # per side, room for epoxy

# MX-style cross socket (Choc V2 uses an MX-compatible stem)
H_SLOT_LEN, H_SLOT_W = 4.30, 1.30       # arm along X (cap width)
V_SLOT_LEN, V_SLOT_W = 4.30, 1.17       # arm along Y
TOOL_D = 1.0                            # cross is cut with this bit
END_EXT = TOOL_D / 2                    # arm ends extended so round tool ends clear square stem

TEST_OFFSETS = [-0.06, -0.03, 0.0, 0.03, 0.06, 0.09]
TEST_PITCH = 9.0

MARGIN = 5.0
BULGE_90 = math.tan(math.radians(90) / 4)  # quarter-arc bulge


# ---- geometry helpers ------------------------------------------------------
def rounded_rect(msp, cx, cy, w, h, r, layer):
    x0, x1, y0, y1 = cx - w / 2, cx + w / 2, cy - h / 2, cy + h / 2
    b = BULGE_90
    pts = [
        (x0 + r, y0, 0), (x1 - r, y0, b),
        (x1, y0 + r, 0), (x1, y1 - r, b),
        (x1 - r, y1, 0), (x0 + r, y1, b),
        (x0, y1 - r, 0), (x0, y0 + r, b),
    ]
    msp.add_lwpolyline(pts, format="xyb", close=True, dxfattribs={"layer": layer})


def cross(msp, cx, cy, offset, layer, rotate=False):
    a = H_SLOT_LEN / 2 + END_EXT          # half length of X arm
    b = (H_SLOT_W + offset) / 2           # half width of X arm
    c = (V_SLOT_W + offset) / 2           # half width of Y arm
    d = V_SLOT_LEN / 2 + END_EXT          # half length of Y arm
    pts = [(a, -b), (a, b), (c, b), (c, d), (-c, d), (-c, b),
           (-a, b), (-a, -b), (-c, -b), (-c, -d), (c, -d), (c, -b)]
    if rotate:
        pts = [(-y, x) for x, y in pts]
    msp.add_lwpolyline([(cx + x, cy + y) for x, y in pts], close=True,
                       dxfattribs={"layer": layer})


def new_doc(layers):
    doc = ezdxf.new("R2010", setup=False)
    doc.units = ezdxf.units.MM
    for name, color in layers:
        doc.layers.add(name, color=color)
    return doc, doc.modelspace()


def grid(n, cols, w, h, gap):
    rows = math.ceil(n / cols)
    for i in range(n):
        col, row = i % cols, rows - 1 - i // cols
        yield (MARGIN + w / 2 + col * (w + gap), MARGIN + h / 2 + row * (h + gap))


# ---- files -----------------------------------------------------------------
def caps(out):
    doc, msp = new_doc([("POCKET_3mm", 5), ("OUTLINE_THRU", 1)])
    for cx, cy in grid(N_CAPS, COLS, CAP_W, CAP_H, CAP_GAP):
        rounded_rect(msp, cx, cy, INS_W + 2 * POCKET_CLEAR, INS_H + 2 * POCKET_CLEAR,
                     INS_R + POCKET_CLEAR, "POCKET_3mm")
        rounded_rect(msp, cx, cy, CAP_W, CAP_H, CAP_R, "OUTLINE_THRU")
    doc.saveas(out)


def inserts(out, offset):
    doc, msp = new_doc([("CROSS_THRU", 3), ("OUTLINE_THRU", 1)])
    for cx, cy in grid(N_CAPS, COLS, INS_W, INS_H, INS_GAP):
        cross(msp, cx, cy, offset, "CROSS_THRU")
        rounded_rect(msp, cx, cy, INS_W, INS_H, INS_R, "OUTLINE_THRU")
    doc.saveas(out)


def test_strip(out):
    doc, msp = new_doc([("CROSS_THRU", 3), ("OUTLINE_THRU", 1)])
    n = len(TEST_OFFSETS)
    w = (n + 1) * TEST_PITCH            # one extra pitch for the marker hole
    h = 2 * TEST_PITCH + 4
    x0, y0 = MARGIN, MARGIN
    rounded_rect(msp, x0 + w / 2, y0 + h / 2, w, h, 2.0, "OUTLINE_THRU")
    # marker hole at the "smallest" end so the strip reads left -> right
    msp.add_circle((x0 + TEST_PITCH / 2, y0 + h / 2), 1.0, dxfattribs={"layer": "CROSS_THRU"})
    for i, off in enumerate(TEST_OFFSETS):
        cx = x0 + TEST_PITCH * (i + 1.5)
        cross(msp, cx, y0 + 2 + TEST_PITCH * 1.5, off, "CROSS_THRU")             # row A: normal
        cross(msp, cx, y0 + 2 + TEST_PITCH * 0.5, off, "CROSS_THRU", rotate=True)  # row B: 90 deg
    doc.saveas(out)


def preview(paths, out):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from ezdxf.addons.drawing import RenderContext, Frontend
        from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
        from ezdxf.addons.drawing.config import Configuration, BackgroundPolicy
    except ImportError:
        return
    fig, axes = plt.subplots(1, len(paths), figsize=(6 * len(paths), 4.5))
    for ax, p in zip(axes, paths):
        doc = ezdxf.readfile(p)
        cfg = Configuration(background_policy=BackgroundPolicy.WHITE)
        Frontend(RenderContext(doc), MatplotlibBackend(ax), config=cfg).draw_layout(doc.modelspace())
        ax.set_title(Path(p).name)
        ax.set_aspect("equal")
    fig.tight_layout()
    fig.savefig(out, dpi=150)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--offset", type=float, default=0.0)
    args = ap.parse_args()
    here = Path(__file__).parent
    files = [here / "caps_wood_6mm.dxf", here / "inserts_alu_3mm.dxf", here / "test_strip_alu_3mm.dxf"]
    caps(files[0])
    inserts(files[1], args.offset)
    test_strip(files[2])
    preview(files, here / "preview.png")
    print("wrote:", *[f.name for f in files], "(insert slot offset %+.2f mm)" % args.offset)

#!/usr/bin/env python3
"""Build a fully native (vector-only) PPTX reconstruction of Fig.5."""
import json, math, os
from pptx import Presentation
from pptx.util import Emu, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE
from pptx.oxml.ns import qn
from lxml import etree

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SHAPES = json.load(open(os.path.join(ROOT, "data", "shapes.json")))
TEXT_SHAPES = json.load(open(os.path.join(ROOT, "data", "text_shapes.json")))
OUTLINE = True
OUT = os.path.join(ROOT, "outputs", "fig5_native_outline_v1.pptx" if OUTLINE else "fig5_native_editable_v1.pptx")

PX = 9144                 # EMU per target pixel (100 px/inch)
W_PX, H_PX = 1536, 1024

# ---- palette (sampled from target) ----
BG       = RGBColor(0xFD, 0xFD, 0xFE)
NAVY     = RGBColor(0x1D, 0x4B, 0x73)
TEAL     = RGBColor(0x0D, 0x7D, 0x88)
ORANGE   = RGBColor(0xE3, 0x67, 0x28)
TEXT     = RGBColor(0x0B, 0x1F, 0x3F)
LTEAL    = RGBColor(0xE9, 0xF6, 0xF6)
LORANGE  = RGBColor(0xFD, 0xF0, 0xE7)
DIVIDER  = RGBColor(0x9C, 0xAF, 0xBE)
WAVE_NAVY = RGBColor(0x1E, 0x3A, 0x5F)
WAVE_TEAL = RGBColor(0x0E, 0x7C, 0x86)

SERIF = "Georgia"
SANS  = "Avenir Next"


def strip_style(shp):
    el = shp._element.find(qn("p:style"))
    if el is not None:
        shp._element.remove(el)


def E(px):
    return Emu(int(round(px * PX)))


def rect(slide, x, y, w, h, fill, line=None, lw=3, radius=10):
    shp = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, E(x), E(y), E(w), E(h))
    shp.adjustments[0] = max(0.0, min(0.5, radius / min(w, h)))
    if fill is None:
        shp.fill.background()
    else:
        shp.fill.solid(); shp.fill.fore_color.rgb = fill
    if line is None:
        shp.line.fill.background()
    else:
        shp.line.color.rgb = line; shp.line.width = Pt(lw * 0.72)  # px -> pt
    shp.shadow.inherit = False
    strip_style(shp)
    return shp


def header_band(slide, x, y, w, h, fill, radius=10, seg=10):
    """Rounded top corners, square bottom corners."""
    sp = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, E(x), E(y), E(w), E(h))
    shp_w, shp_h = int(w * PX), int(h * PX)
    spPr = sp._element.spPr
    for tag in ("a:prstGeom", "a:solidFill", "a:ln"):
        for e in spPr.findall(qn(tag)):
            spPr.remove(e)
    cg = etree.SubElement(spPr, qn("a:custGeom"))
    for tag in ("a:avLst", "a:gdLst", "a:ahLst", "a:cxnLst"):
        etree.SubElement(cg, qn(tag))
    r = etree.SubElement(cg, qn("a:rect")); r.set("l", "0"); r.set("t", "0"); r.set("r", "r"); r.set("b", "b")
    pl = etree.SubElement(cg, qn("a:pathLst"))
    path = etree.SubElement(pl, qn("a:path")); path.set("w", str(shp_w)); path.set("h", str(shp_h))
    R = radius * PX
    pts = []
    # start at left edge below top-left corner, go up around corner
    pts.append((0, R))
    for i in range(seg + 1):
        a = math.pi + (math.pi / 2) * i / seg
        pts.append((R + R * math.cos(a), R + R * math.sin(a)))
    pts.append((shp_w - R, 0))
    for i in range(seg + 1):
        a = -math.pi / 2 + (math.pi / 2) * i / seg
        pts.append((shp_w - R + R * math.cos(a), R + R * math.sin(a)))
    pts.append((shp_w, shp_h))
    pts.append((0, shp_h))
    mt = etree.SubElement(path, qn("a:moveTo"))
    p = etree.SubElement(mt, qn("a:pt")); p.set("x", str(int(pts[0][0]))); p.set("y", str(int(pts[0][1])))
    for (px, py) in pts[1:]:
        ln = etree.SubElement(path, qn("a:lnTo"))
        q = etree.SubElement(ln, qn("a:pt")); q.set("x", str(int(px))); q.set("y", str(int(py)))
    etree.SubElement(path, qn("a:close"))
    sf = etree.SubElement(spPr, qn("a:solidFill"))
    c = etree.SubElement(sf, qn("a:srgbClr")); c.set("val", str(fill))
    ln = etree.SubElement(spPr, qn("a:ln")); etree.SubElement(ln, qn("a:noFill"))
    sp.shadow.inherit = False
    strip_style(sp)
    return sp


def text(slide, x, y, w, h, s, font, size, color, bold=False, align=PP_ALIGN.CENTER,
         anchor=MSO_ANCHOR.MIDDLE, spacing=None, char_spacing=None, italic=False, wrap=True):
    tb = slide.shapes.add_textbox(E(x), E(y), E(w), E(h))
    tf = tb.text_frame
    tf.word_wrap = wrap
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = anchor
    lines = s.split("\n")
    for i, line in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        if spacing is not None:
            p.line_spacing = spacing
        r = p.add_run(); r.text = line
        r.font.name = font; r.font.size = Pt(size); r.font.bold = bold; r.font.italic = italic
        r.font.color.rgb = color
        if char_spacing:
            r._r.get_or_add_rPr().set("spc", str(int(char_spacing * 100)))
    return tb


def maybe_text(*a, **k):
    if not OUTLINE:
        return text(*a, **k)
    return None


def draw_text_outline(slide, name):
    d = TEXT_SHAPES[name]
    contours = d["contours"]
    groups = _groups(contours)
    groups.sort(key=lambda g: _area(contours[g[0]]), reverse=True)
    for grp in groups:
        _add_path_shape(slide, [contours[grp[0]]], d["fill"])
        for hi in grp[1:]:
            _add_path_shape(slide, [contours[hi]], d["hole"])


def _area(c):
    a = 0.0
    for i in range(len(c)):
        x1, y1 = c[i]; x2, y2 = c[(i + 1) % len(c)]
        a += x1 * y2 - x2 * y1
    return abs(a) * 0.5


def _contains(poly, pt):
    x, y = pt; inside = False
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]; x2, y2 = poly[(i + 1) % n]
        if (y1 > y) != (y2 > y):
            xi = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
            if x < xi:
                inside = not inside
    return inside


def _groups(contours):
    """Group even-depth outer contours with their immediate holes."""
    n = len(contours)
    depth = []
    for i in range(n):
        pt = contours[i][0]
        depth.append(sum(1 for j in range(n) if j != i and _contains(contours[j], pt)))
    outers = [i for i in range(n) if depth[i] % 2 == 0]
    groups = {i: [i] for i in outers}
    for i in range(n):
        if depth[i] % 2 == 1:
            if _area(contours[i]) < 5.0:
                continue
            cands = [j for j in outers if depth[j] == depth[i] - 1 and _contains(contours[j], contours[i][0])]
            if cands:
                j = min(cands, key=lambda k: _area(contours[k]))
                groups[j].append(i)
            else:
                groups[i] = [i]
    return [groups[k] for k in groups]


def _add_path_shape(slide, contours, color, bbox=None):
    pts_all = [p for c in contours for p in c]
    x0 = min(p[0] for p in pts_all); x1 = max(p[0] for p in pts_all)
    y0 = min(p[1] for p in pts_all); y1 = max(p[1] for p in pts_all)
    if bbox is not None:
        x0, y0, x1, y1 = bbox
    w, h = (x1 - x0), (y1 - y0)
    if w <= 0 or h <= 0:
        return None
    sw, sh = int(w * PX), int(h * PX)
    ff = slide.shapes.build_freeform(0, 0, scale=1)
    ff.add_line_segments([(1, 0), (1, 1), (0, 1)], close=True)
    shp = ff.convert_to_shape()
    shp.left, shp.top = E(x0), E(y0)
    shp.width, shp.height = Emu(sw), Emu(sh)
    spPr = shp._element.spPr
    for tag in ("a:solidFill", "a:ln"):
        for e in spPr.findall(qn(tag)):
            spPr.remove(e)
    cg = spPr.find(qn("a:custGeom"))
    pl = cg.find(qn("a:pathLst"))
    for e in list(pl):
        pl.remove(e)
    path = etree.SubElement(pl, qn("a:path")); path.set("w", str(sw)); path.set("h", str(sh))
    for c in contours:
        pts = [((px - x0) * PX, (py - y0) * PX) for px, py in c]
        mt = etree.SubElement(path, qn("a:moveTo"))
        p = etree.SubElement(mt, qn("a:pt")); p.set("x", str(int(pts[0][0]))); p.set("y", str(int(pts[0][1])))
        for (px, py) in pts[1:]:
            ln = etree.SubElement(path, qn("a:lnTo"))
            q = etree.SubElement(ln, qn("a:pt")); q.set("x", str(int(px))); q.set("y", str(int(py)))
        etree.SubElement(path, qn("a:close"))
    sf = etree.SubElement(spPr, qn("a:solidFill"))
    c = etree.SubElement(sf, qn("a:srgbClr")); c.set("val", str(color).lstrip("#").upper())
    ln = etree.SubElement(spPr, qn("a:ln")); etree.SubElement(ln, qn("a:noFill"))
    strip_style(shp)
    return shp


def traced(slide, name, cmap, bbox=None):
    """Add shapes: outer contour filled, holes as card-coloured overlays."""
    data = SHAPES[name]
    contours = data["colors"][cmap]
    if not contours:
        return None
    groups = _groups(contours)
    groups.sort(key=lambda g: _area(contours[g[0]]), reverse=True)
    out = []
    for grp in groups:
        outer = contours[grp[0]]
        shp = _add_path_shape(slide, [outer], {"navy": WAVE_NAVY, "teal": WAVE_TEAL}[cmap])
        if shp is not None:
            out.append(shp)
        for hi in grp[1:]:
            hole = _add_path_shape(slide, [contours[hi]], RGBColor(0xFF, 0xFF, 0xFF))
            if hole is not None:
                hole.name = "hole"
                out.append(hole)
    return out


def icon_color(name, cmap):
    if cmap == "navy":
        return NAVY
    if cmap == "teal":
        return TEAL
    return WAVE_NAVY


def traced_colored(slide, name, cmap, color):
    shps = traced(slide, name, cmap) or []
    for shp in shps:
        if shp.name.startswith("hole"):
            continue
        sf = shp._element.spPr.find(qn("a:solidFill"))
        clr = sf.find(qn("a:srgbClr"))
        clr.set("val", str(color))
    return shps


def circle_icon(slide, cx, cy, r, color, mark):
    """Check / cross badge: ring + mark, all vector."""
    shp = slide.shapes.add_shape(MSO_SHAPE.OVAL, E(cx - r), E(cy - r), E(2 * r), E(2 * r))
    shp.fill.background()
    shp.line.color.rgb = color; shp.line.width = Pt(3.2)
    shp.shadow.inherit = False
    if mark == "check":
        pts = [(cx - r * 0.45, cy + r * 0.02), (cx - r * 0.12, cy + r * 0.36), (cx + r * 0.5, cy - r * 0.32)]
    else:
        pts = None
    if pts:
        ff = slide.shapes.build_freeform(int(pts[0][0] * PX), int(pts[0][1] * PX), scale=1)
        ff.add_line_segments([(int(x * PX), int(y * PX)) for x, y in pts[1:]], close=False)
        ln = ff.convert_to_shape()
        ln.fill.background()
        ln.line.color.rgb = color; ln.line.width = Pt(4.2)
        ln.shadow.inherit = False
        # round caps
        lnEl = ln.line._get_or_add_ln(); lnEl.set("cap", "rnd")
    else:
        # X as an explicit 12-point polygon (more robust than folded lines)
        L = r * 0.50; t = r * 0.16
        ca, sa = math.cos(math.pi / 4), math.sin(math.pi / 4)
        a = (ca, sa); b = (-sa, ca)
        raw = [(-L, +t), (-t, +t), (-t, +L), (+t, +L), (+t, +t), (+L, +t),
               (+L, -t), (+t, -t), (+t, -L), (-t, -L), (-t, -t), (-L, -t)]
        pts = [(cx + u * a[0] + v * b[0], cy + u * a[1] + v * b[1]) for u, v in raw]
        ff = slide.shapes.build_freeform(int(pts[0][0] * PX), int(pts[0][1] * PX), scale=1)
        ff.add_line_segments([(int(px * PX), int(py * PX)) for px, py in pts[1:]], close=True)
        xsh = ff.convert_to_shape()
        xsh.fill.solid(); xsh.fill.fore_color.rgb = color
        xsh.line.fill.background(); xsh.shadow.inherit = False


def arrow(slide, x, y, w, h):
    shp = slide.shapes.add_shape(MSO_SHAPE.RIGHT_ARROW, E(x), E(y), E(w), E(h))
    shp.fill.solid(); shp.fill.fore_color.rgb = RGBColor(0x1B, 0x3A, 0x5B)
    shp.line.fill.background(); shp.shadow.inherit = False
    shp.adjustments[0] = 0.45
    shp.adjustments[1] = 0.55


def build():
    prs = Presentation()
    prs.slide_width = E(W_PX)
    prs.slide_height = E(H_PX)
    s = prs.slides.add_slide(prs.slide_layouts[6])

    # background
    bg = rect(s, 0, 0, W_PX, H_PX, BG, radius=0)

    # ---------- title ----------
    maybe_text(s, 98, 24, 1306, 72, "Which signal-processing priors transfer across subjects?",
         SERIF, 29.1, TEXT, bold=True, wrap=False)

    # ---------- three protocol cards ----------
    cards = [
        dict(x=31, color=NAVY,   hdr="PRIMARY EVIDENCE", num="1", cdx=57, hx=116, hspc=0.50,
             body="PhysioNet EEGMMI, native\nleft/right binary, 109-subject LOSO",
             icons=[("head1", "navy", NAVY), ("handL1", "navy", NAVY), ("handR1", "teal", TEAL)],
             labels=[("L", 294, 424), ("R", 390, 424)],
             waves="wave1"),
        dict(x=539, color=TEAL,  hdr="SECONDARY REPLICATION", num="2", cdx=49, hx=100, hspc=-0.90,
             body="PhysioNet EEGMMI, native\nfists/feet binary, 109-subject LOSO",
             icons=[("head2", "navy", NAVY), ("fist2", "navy", NAVY), ("foot2", "teal", TEAL)],
             labels=[("Fists", 792, 424), ("Feet", 913, 424)],
             waves="wave2"),
        dict(x=1048, color=ORANGE, hdr="EXTERNAL BOUNDARY TEST", num="3", cdx=50, hx=102, hspc=-1.35,
             body="BCI Competition IV-2a,\n9-subject cross-session, four-class",
             icons=[("head3", "navy", NAVY), ("handL3", "navy", NAVY), ("handR3", "teal", TEAL),
                    ("feet3", "teal", TEAL), ("tongue3", "navy", NAVY)],
             labels=[("Left\nHand", 1226, 410), ("Right\nHand", 1302, 410),
                     ("Both\nFeet", 1378, 410), ("Tongue", 1459, 410)],
             waves="wave3"),
    ]
    CARD_W, CARD_H, CARD_Y, HDR_H = 457, 453, 133, 79
    BODY = {31: (22.5, 19.6), 539: (20.5, 19.6), 1048: (11.5, 19.9)}

    for c in cards:
        x = c["x"]
        # body fill + border
        rect(s, x, CARD_Y, CARD_W, CARD_H, RGBColor(0xFF, 0xFF, 0xFF), line=c["color"], lw=3, radius=10)
        header_band(s, x, CARD_Y, CARD_W, HDR_H, c["color"], radius=10)
        # number circle
        cx, cy, r = x + c["cdx"], CARD_Y + 39, 30
        circ = s.shapes.add_shape(MSO_SHAPE.OVAL, E(cx - r), E(cy - r), E(2 * r), E(2 * r))
        circ.fill.background(); circ.line.color.rgb = RGBColor(0xFF, 0xFF, 0xFF); circ.line.width = Pt(2.6)
        circ.shadow.inherit = False
        text(s, cx - r, cy - r - 2, 2 * r, 2 * r, c["num"], SERIF, 22, RGBColor(0xFF, 0xFF, 0xFF), bold=True)
        # header text
        maybe_text(s, x + c["hx"], CARD_Y + 12, CARD_W - c["hx"] + 60, HDR_H - 20, c["hdr"], SANS, 19.2,
             RGBColor(0xFF, 0xFF, 0xFF), bold=True, align=PP_ALIGN.LEFT,
             char_spacing=c["hspc"], wrap=False)
        # body text
        bdx, bfs = BODY[x]
        maybe_text(s, x + bdx, 219, CARD_W - 20, 84, c["body"], SERIF, bfs, TEXT, spacing=1.15, wrap=False)
        # icons
        for nm, cm, col in c["icons"]:
            traced_colored(s, nm, cm, col)
        # labels
        for lab, lx, ly in c["labels"]:
            if "\n" in lab:
                text(s, lx - 36, ly, 72, 50, lab, SERIF, 15.2, TEXT, spacing=1.02)
            elif lab in ("L", "R"):
                text(s, lx - 25, ly, 50, 26, lab, SERIF, 21, TEXT)
            else:
                lsz = 13.5 if lab == "Tongue" else 19
                text(s, lx - 45, ly, 90, 26, lab, SERIF, lsz, TEXT)
        if c["x"] == 1048:
            for sx in (1341, 1416):
                ln = s.shapes.add_connector(1, E(sx), E(320), E(sx), E(400))
                ln.line.color.rgb = RGBColor(0xA9, 0xB7, 0xC4); ln.line.width = Pt(1.2)
        # waveform
        traced_colored(s, c["waves"], "navy", WAVE_NAVY)
        traced_colored(s, c["waves"], "teal", WAVE_TEAL)

    # arrows
    arrow(s, 490, 342, 46, 40)
    arrow(s, 998, 342, 46, 40)

    # ---------- divider ----------
    line = s.shapes.add_connector(1, E(18), E(627), E(1518), E(627))  # straight
    line.line.color.rgb = DIVIDER; line.line.width = Pt(1.6)
    tri = s.shapes.build_freeform(int(752 * PX), int(600 * PX), scale=1)
    tri.add_line_segments([(int(784 * PX), int(600 * PX)), (int(768 * PX), int(627 * PX))], close=True)
    tri = tri.convert_to_shape(); tri.fill.solid(); tri.fill.fore_color.rgb = DIVIDER
    tri.line.fill.background(); tri.shadow.inherit = False

    # ---------- bottom cards ----------
    for x, y, w, h, col, fill, hdr, body in [
        (33, 672, 854, 267, TEAL, LTEAL, "SUPPORTED CLAIM",
         "Preserving temporal dynamics is safer than\naggressive explicit-band processing followed\nby early temporal collapse."),
        (914, 672, 586, 267, ORANGE, LORANGE, "NOT CLAIMED",
         "No universal winner across\ndatasets or tasks."),
    ]:
        rect(s, x, y, w, h, fill, line=col, lw=3, radius=12)
        header_band(s, x, y, w, 85, col, radius=12)
        tx = 165 if x < 500 else 1035
        maybe_text(s, tx, y + 18, w - (tx - x) - 20, 58, hdr, SANS, 22.7, RGBColor(0xFF, 0xFF, 0xFF),
             bold=True, align=PP_ALIGN.LEFT, char_spacing=0, wrap=False)
        bw = 25.8 if x < 500 else 26.2
        maybe_text(s, x + 20, y + 94, w - 40, h - 108, body, SERIF, bw, TEXT, spacing=1.15)

    circle_icon(s, 96, 714, 32, RGBColor(0xFF, 0xFF, 0xFF), "check")
    circle_icon(s, 973, 714, 32, RGBColor(0xFF, 0xFF, 0xFF), "cross")

    if OUTLINE:
        for name in ("title", "c1_hdr", "c2_hdr", "c3_hdr", "c1_body", "c2_body", "c3_body",
                     "b1_hdr", "b2_hdr", "b1_body", "b2_body"):
            draw_text_outline(s, name)

    for sh in s.shapes:
        el = sh._element.find(qn("p:style"))
        if el is not None:
            sh._element.remove(el)

    prs.save(OUT)
    print("wrote", OUT)


if __name__ == "__main__":
    import sys
    if "--editable" in sys.argv:
        OUTLINE = False
        OUT = os.path.join(ROOT, "outputs", "fig5_native_editable_v1.pptx")
    build()

"""
Generate architecture and data flow diagrams for JiraMaster README.
Uses only Python stdlib + Pillow (already available).
"""
from PIL import Image, ImageDraw, ImageFont
import os

OUT = os.path.join(os.path.dirname(__file__), "images")
os.makedirs(OUT, exist_ok=True)

# ─── Color palette ────────────────────────────────────────────────────────────
BG        = (248, 250, 252)    # page background
BOX_BLUE  = (30, 136, 229)     # Flask / route boxes
BOX_TEAL  = (0, 150, 136)      # data store boxes
BOX_ORG   = (251, 140, 0)      # external (Jira, LLM)
BOX_GRAY  = (96, 125, 139)     # utility modules
BOX_WHITE = (255, 255, 255)
TEXT_W    = (255, 255, 255)
TEXT_D    = (33, 33, 33)
BORDER    = (189, 189, 189)
ARROW     = (55, 71, 79)
LINE_LT   = (207, 216, 220)    # light connector line


def load_font(size):
    """Try to load a system font, fall back to default."""
    candidates = [
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/SFNSText.ttf",
        "/System/Library/Fonts/Arial.ttf",
        "/Library/Fonts/Arial.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                pass
    return ImageFont.load_default()


def text_size(draw, text, font):
    bb = draw.textbbox((0, 0), text, font=font)
    return bb[2] - bb[0], bb[3] - bb[1]


def draw_rounded_rect(draw, xy, radius=10, fill=None, outline=None, width=2):
    x0, y0, x1, y1 = xy
    draw.rounded_rectangle([x0, y0, x1, y1], radius=radius, fill=fill, outline=outline, width=width)


def draw_arrow(draw, start, end, color=ARROW, width=2, head=10):
    """Draw a straight arrow from start to end."""
    import math
    draw.line([start, end], fill=color, width=width)
    # arrowhead
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    length = math.hypot(dx, dy)
    if length == 0:
        return
    ux, uy = dx / length, dy / length
    px, py = -uy, ux
    tip = end
    left  = (tip[0] - head * ux + head * 0.4 * px, tip[1] - head * uy + head * 0.4 * py)
    right = (tip[0] - head * ux - head * 0.4 * px, tip[1] - head * uy - head * 0.4 * py)
    draw.polygon([tip, left, right], fill=color)


def centered_text(draw, cx, cy, text, font, color=TEXT_W):
    w, h = text_size(draw, text, font)
    draw.text((cx - w // 2, cy - h // 2), text, font=font, fill=color)


# ══════════════════════════════════════════════════════════════════════════════
# DIAGRAM 1 — System Architecture
# ══════════════════════════════════════════════════════════════════════════════
def diagram_architecture():
    W, H = 1400, 860
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    f_title = load_font(26)
    f_head  = load_font(18)
    f_body  = load_font(14)
    f_sm    = load_font(12)
    f_xs    = load_font(11)

    # ── Title ─────────────────────────────────────────────────────────────────
    centered_text(draw, W // 2, 36, "JiraMaster v1.8 — System Architecture", f_title, TEXT_D)

    # ── Section label helper ──────────────────────────────────────────────────
    def section_label(x, y, label):
        w, h = text_size(draw, label, f_xs)
        draw.text((x - w // 2, y), label, font=f_xs, fill=(120, 120, 120))

    # ── Box helper ────────────────────────────────────────────────────────────
    def box(x, y, w, h, title, subtitle=None, color=BOX_BLUE, text_color=TEXT_W, radius=10):
        draw_rounded_rect(draw, [x, y, x + w, y + h], radius=radius, fill=color, outline=None)
        if subtitle:
            centered_text(draw, x + w // 2, y + h // 2 - 10, title, f_body, text_color)
            centered_text(draw, x + w // 2, y + h // 2 + 10, subtitle, f_xs, text_color)
        else:
            centered_text(draw, x + w // 2, y + h // 2, title, f_body, text_color)

    # ── Browser (User) ────────────────────────────────────────────────────────
    bx, by, bw, bh = 30, 108, 155, 70
    box(bx, by, bw, bh, "Browser", "(User)", color=(69, 90, 100))
    section_label(bx + bw // 2, by - 22, "CLIENT")

    # ── Flask App container ───────────────────────────────────────────────────
    fx, fy, fw, fh = 210, 80, 880, 130
    draw_rounded_rect(draw, [fx, fy, fx + fw, fy + fh], radius=14,
                      fill=(236, 242, 255), outline=(30, 136, 229), width=2)
    centered_text(draw, fx + fw // 2, fy + 20, "Flask Application  (app.py)", f_head, BOX_BLUE)
    section_label(fx + fw // 2, fy - 22, "APPLICATION LAYER")

    # Route boxes inside Flask — 8 routes, 88px wide each
    routes = [
        ("/ home",    220, 112),
        ("/prompt",   316, 112),
        ("/import",   412, 112),
        ("/edit",     508, 112),
        ("/upload",   604, 112),
        ("/settings", 700, 112),
        ("/tools",    796, 112),
        ("/cache",    892, 112),
    ]
    for label, rx, ry in routes:
        box(rx, ry, 88, 44, label, color=BOX_BLUE, radius=7)

    # Security annotation below routes
    sec_text = "CSRF · Security Headers · Session Fingerprinting · HttpOnly Cookies"
    sw, _ = text_size(draw, sec_text, f_xs)
    draw.text((fx + fw // 2 - sw // 2, fy + fh - 18), sec_text, font=f_xs, fill=(60, 100, 180))

    # ── Core Modules ──────────────────────────────────────────────────────────
    modules_y = 278
    modules = [
        ("parser.py",         "YAML/JSON → Epics",  BOX_GRAY),
        ("prompt_builder.py", "Prompt Generation",  BOX_GRAY),
        ("jira_client.py",    "Jira REST API v3",   BOX_BLUE),
        ("config.py",         "Config + Keyring",   BOX_GRAY),
        ("models.py",         "Dataclasses",        BOX_GRAY),
        ("work_store.py",     "Session Store",      BOX_GRAY),
        ("logging_config.py", "Centralised Logs",   BOX_GRAY),
    ]
    mw, mh = 178, 68
    gap = 18
    mx_start = 30
    for i, (name, desc, color) in enumerate(modules):
        mx = mx_start + i * (mw + gap)
        box(mx, modules_y, mw, mh, name, desc, color=color)
    section_label(W // 2, modules_y - 22, "CORE MODULES")

    # Connectors: Flask → modules
    for i in range(len(modules)):
        mx = mx_start + i * (mw + gap) + mw // 2
        draw_arrow(draw, (fx + fw // 2, fy + fh), (mx, modules_y), width=1, head=7)

    # ── File Storage ──────────────────────────────────────────────────────────
    store_y = 420
    stores = [
        (".work/{uuid}.json", "Session Work Files"),
        ("config.json",       "Jira Credentials"),
        ("cache/assignees",   "Assignee Cache"),
        ("cache/labels",      "Label Cache"),
        ("cache/projects",    "Project Cache"),
        ("logs/",             "App + Startup Logs"),
    ]
    sw2, sh = 185, 62
    sg = 20
    sx_start = 30
    for i, (name, desc) in enumerate(stores):
        sx = sx_start + i * (sw2 + sg)
        box(sx, store_y, sw2, sh, name, desc, color=BOX_TEAL, radius=8)
    section_label(W // 2, store_y - 22, "FILE STORAGE  (no database)")

    # Connectors: core modules → storage
    draw_arrow(draw, (mx_start + 2 * (mw + gap) + mw // 2, modules_y + mh),
               (sx_start + sw2 // 2, store_y), width=1, head=7)
    draw_arrow(draw, (mx_start + 3 * (mw + gap) + mw // 2, modules_y + mh),
               (sx_start + sw2 + sg + sw2 // 2, store_y), width=1, head=7)
    draw_arrow(draw, (mx_start + 5 * (mw + gap) + mw // 2, modules_y + mh),
               (sx_start + sw2 // 2, store_y), width=1, head=7)

    # ── External Services ─────────────────────────────────────────────────────
    ext_y = 278
    externals = [
        ("Jira Cloud",       "REST API v3"),
        ("Atlassian Teams",  "Teams API"),
        ("OS Keyring",       "macOS / Windows"),
    ]
    ex, ey_start = 1150, ext_y
    ew, eh = 200, 68
    eg = 18
    for i, (name, desc) in enumerate(externals):
        ey = ey_start + i * (eh + eg)
        box(ex, ey, ew, eh, name, desc, color=BOX_ORG)
    section_label(ex + ew // 2, ext_y - 22, "EXTERNAL")

    # Connector: jira_client → Jira Cloud
    jira_mx = mx_start + 2 * (mw + gap) + mw
    draw_arrow(draw, (jira_mx, modules_y + mh // 2), (ex, ext_y + eh // 2), width=2, head=10)
    # Connector: config.py → OS Keyring
    cfg_mx = mx_start + 3 * (mw + gap) + mw
    draw_arrow(draw, (cfg_mx, modules_y + mh // 2), (ex, ext_y + 2 * (eh + eg) + eh // 2), width=1, head=7)

    # ── LLM (manual out-of-band) ──────────────────────────────────────────────
    lx, ly, lw, lh = 1150, 108, 200, 62
    box(lx, ly, lw, lh, "LLM", "(Copilot / ChatGPT)", color=BOX_ORG)
    draw.line([(bx + bw, by + bh // 2), (lx, ly + lh // 2)], fill=(200, 200, 200), width=2)
    draw.text((850, by + bh // 2 - 16), "copy prompt / paste output", font=f_xs, fill=(160, 160, 160))

    # Browser ↔ Flask
    draw_arrow(draw, (bx + bw, by + bh // 2), (fx, fy + fh // 2), width=2, head=10)
    draw_arrow(draw, (fx, fy + fh // 2 + 14), (bx + bw, by + bh // 2 + 14), width=2, head=10)

    # ── Launch Scripts ────────────────────────────────────────────────────────
    lsx, lsy, lsw, lsh = 260, 570, 420, 62
    box(lsx, lsy, lsw, lsh, "start.sh / start.ps1 / start.bat",
        "venv · deps · CA cert merge · launch", color=(78, 52, 46), radius=8)
    section_label(lsx + lsw // 2, lsy - 22, "LAUNCH SCRIPTS")
    draw_arrow(draw, (lsx + lsw // 2, lsy), (fx + fw // 2, fy + fh), width=1, head=8)

    # ── Legend ────────────────────────────────────────────────────────────────
    legend_items = [
        (BOX_BLUE,    "Flask / Routes / Jira Client"),
        (BOX_GRAY,    "Core Modules"),
        (BOX_TEAL,    "File Storage"),
        (BOX_ORG,     "External Services"),
        ((78, 52, 46),"Launch Scripts"),
    ]
    lx0, ly0 = 30, 720
    for i, (color, label) in enumerate(legend_items):
        cx = lx0 + i * 260
        draw_rounded_rect(draw, [cx, ly0, cx + 20, ly0 + 20], radius=4, fill=color)
        draw.text((cx + 28, ly0 + 2), label, font=f_xs, fill=TEXT_D)

    img.save(os.path.join(OUT, "architecture.png"), "PNG", dpi=(144, 144))
    print("✓ architecture.png")


# ══════════════════════════════════════════════════════════════════════════════
# DIAGRAM 2 — Data Flow (4-step wizard)
# ══════════════════════════════════════════════════════════════════════════════
def diagram_dataflow():
    W, H = 1300, 580
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    f_title = load_font(24)
    f_head  = load_font(17)
    f_body  = load_font(14)
    f_sm    = load_font(12)

    centered_text(draw, W // 2, 34, "JiraMaster — 4-Step Workflow", f_title, TEXT_D)

    # Steps layout
    steps = [
        {
            "num": "1",
            "title": "Prompt",
            "color": (30, 136, 229),
            "lines": ["Paste meeting notes", "Tune parameters", "Generate LLM prompt", "Copy / Download .txt"],
        },
        {
            "num": "2",
            "title": "Import",
            "color": (0, 150, 136),
            "lines": ["Paste / Upload", "YAML or JSON output", "Select epics & stories", "Set initiative IDs"],
        },
        {
            "num": "3",
            "title": "Edit",
            "color": (123, 31, 162),
            "lines": ["Edit titles & descriptions", "Set acceptance criteria", "Assign users & labels", "Set priorities & dates"],
        },
        {
            "num": "4",
            "title": "Upload",
            "color": (183, 28, 28),
            "lines": ["Preview counts", "Push to Jira Cloud", "View results", "Click links to issues"],
        },
    ]

    box_w, box_h = 220, 260
    gap = 70
    total_w = len(steps) * box_w + (len(steps) - 1) * gap
    start_x = (W - total_w) // 2
    box_y = 90

    for i, step in enumerate(steps):
        x = start_x + i * (box_w + gap)
        color = step["color"]

        # Card shadow
        draw_rounded_rect(draw, [x + 4, box_y + 4, x + box_w + 4, box_y + box_h + 4],
                          radius=14, fill=(220, 220, 220))
        # Card
        draw_rounded_rect(draw, [x, box_y, x + box_w, box_y + box_h],
                          radius=14, fill=BOX_WHITE, outline=color, width=3)

        # Step circle
        cx = x + box_w // 2
        r = 26
        draw.ellipse([cx - r, box_y - r, cx + r, box_y + r], fill=color)
        centered_text(draw, cx, box_y, step["num"], f_head, TEXT_W)

        # Title bar
        draw_rounded_rect(draw, [x, box_y + 30, x + box_w, box_y + 74],
                          radius=0, fill=color)
        draw_rounded_rect(draw, [x, box_y + 30, x + box_w, box_y + 54],
                          radius=0, fill=color)
        centered_text(draw, cx, box_y + 54, step["title"], f_head, TEXT_W)

        # Bullet lines
        for j, line in enumerate(step["lines"]):
            ly = box_y + 88 + j * 38
            # dot
            draw.ellipse([x + 20, ly + 5, x + 28, ly + 13], fill=color)
            draw.text((x + 36, ly), line, font=f_body, fill=TEXT_D)

        # Arrow to next step
        if i < len(steps) - 1:
            ax = x + box_w + 8
            ay = box_y + box_h // 2
            draw_arrow(draw, (ax, ay), (ax + gap - 16, ay), color=ARROW, width=3, head=12)

    # ── Bottom row: storage, Jira Cloud, and Tools/Cache ────────────────────
    mid_y = box_y + box_h + 60

    # Space the three bottom boxes evenly under the 4 steps
    total_bottom_w = 3 * 180 + 2 * 40
    bottom_start_x = (W - total_bottom_w) // 2

    # Work file box
    wfx = bottom_start_x
    draw_rounded_rect(draw, [wfx, mid_y, wfx + 180, mid_y + 56],
                      radius=10, fill=BOX_TEAL, outline=None)
    centered_text(draw, wfx + 90, mid_y + 18, ".work/{uuid}.json", f_body, TEXT_W)
    centered_text(draw, wfx + 90, mid_y + 38, "Session storage", f_sm, TEXT_W)

    # Jira Cloud box
    jcx = bottom_start_x + 180 + 40
    draw_rounded_rect(draw, [jcx, mid_y, jcx + 180, mid_y + 56],
                      radius=10, fill=BOX_ORG, outline=None)
    centered_text(draw, jcx + 90, mid_y + 18, "Jira Cloud", f_body, TEXT_W)
    centered_text(draw, jcx + 90, mid_y + 38, "REST API v3", f_sm, TEXT_W)

    # Jira Tools + Cache box
    tcx = bottom_start_x + 2 * (180 + 40)
    draw_rounded_rect(draw, [tcx, mid_y, tcx + 180, mid_y + 56],
                      radius=10, fill=BOX_TEAL, outline=None)
    centered_text(draw, tcx + 90, mid_y + 18, "Jira Tools + Cache", f_body, TEXT_W)
    centered_text(draw, tcx + 90, mid_y + 38, "cache/ directory", f_sm, TEXT_W)

    # Steps 2+3 → work file
    step2_cx = start_x + (box_w + gap) + box_w // 2
    step3_cx = start_x + 2 * (box_w + gap) + box_w // 2
    draw_arrow(draw, (step2_cx, box_y + box_h), (wfx + 90, mid_y), width=1, head=7)
    draw_arrow(draw, (step3_cx, box_y + box_h), (wfx + 90, mid_y), width=1, head=7)

    # Step 4 → Jira Cloud
    step4_cx = start_x + 3 * (box_w + gap) + box_w // 2
    draw_arrow(draw, (step4_cx, box_y + box_h), (jcx + 90, mid_y), width=2, head=10)

    # Step 1 (prompt) → Tools+Cache box (thin arrow showing tools dependency)
    step1_cx = start_x + box_w // 2
    draw_arrow(draw, (step1_cx, box_y + box_h), (tcx + 90, mid_y), width=1, head=7)

    # ── LLM note ─────────────────────────────────────────────────────────────
    draw.text((40, mid_y + 76), "* User copies prompt to their LLM (Copilot/ChatGPT), then pastes YAML output back into JiraMaster at Step 2",
              font=f_sm, fill=(120, 120, 120))

    img.save(os.path.join(OUT, "dataflow.png"), "PNG", dpi=(144, 144))
    print("✓ dataflow.png")


if __name__ == "__main__":
    diagram_architecture()
    diagram_dataflow()
    print("All diagrams generated in docs/images/")

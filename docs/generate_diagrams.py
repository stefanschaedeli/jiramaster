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
    W, H = 1400, 820
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    f_title = load_font(26)
    f_head  = load_font(18)
    f_body  = load_font(14)
    f_sm    = load_font(12)

    # ── Title ─────────────────────────────────────────────────────────────────
    centered_text(draw, W // 2, 36, "JiraMaster — System Architecture", f_title, TEXT_D)

    # ── Section labels ────────────────────────────────────────────────────────
    def section_label(x, y, label):
        w, h = text_size(draw, label, f_sm)
        draw.text((x - w // 2, y), label, font=f_sm, fill=(120, 120, 120))

    # ── Helper to draw a box with title + optional subtitle ──────────────────
    def box(x, y, w, h, title, subtitle=None, color=BOX_BLUE, text_color=TEXT_W, radius=10):
        draw_rounded_rect(draw, [x, y, x + w, y + h], radius=radius, fill=color, outline=None)
        if subtitle:
            centered_text(draw, x + w // 2, y + h // 2 - 10, title, f_body, text_color)
            centered_text(draw, x + w // 2, y + h // 2 + 10, subtitle, f_sm, text_color)
        else:
            centered_text(draw, x + w // 2, y + h // 2, title, f_body, text_color)

    # ── Browser (User) ────────────────────────────────────────────────────────
    bx, by, bw, bh = 60, 100, 160, 70
    box(bx, by, bw, bh, "Browser", "(User)", color=(69, 90, 100))
    section_label(bx + bw // 2, by - 22, "CLIENT")

    # ── Flask App ─────────────────────────────────────────────────────────────
    fx, fy, fw, fh = 310, 80, 780, 110
    draw_rounded_rect(draw, [fx, fy, fx + fw, fy + fh], radius=14,
                      fill=(236, 242, 255), outline=(30, 136, 229), width=2)
    centered_text(draw, fx + fw // 2, fy + 22, "Flask Application  (app.py)", f_head, BOX_BLUE)
    section_label(fx + fw // 2, fy - 22, "APPLICATION LAYER")

    # Route boxes inside Flask
    routes = [
        ("/prompt", 330, 108),
        ("/import", 460, 108),
        ("/edit",   590, 108),
        ("/upload", 720, 108),
        ("/settings", 850, 108),
        ("/tools",  980, 108),
    ]
    for label, rx, ry in routes:
        box(rx, ry, 100, 46, label, color=BOX_BLUE, radius=8)

    # ── Core Modules ──────────────────────────────────────────────────────────
    modules_y = 250
    modules = [
        ("parser.py", "YAML/JSON → Epics", BOX_GRAY),
        ("prompt_builder.py", "Prompt Generation", BOX_GRAY),
        ("jira_client.py", "Jira REST API v3", BOX_BLUE),
        ("config.py", "Config Load/Save", BOX_GRAY),
        ("models.py", "Dataclasses", BOX_GRAY),
        ("logging_config.py", "Centralised Logs", BOX_GRAY),
    ]
    mx_start = 60
    mw, mh = 190, 70
    gap = 30
    for i, (name, desc, color) in enumerate(modules):
        mx = mx_start + i * (mw + gap)
        box(mx, modules_y, mw, mh, name, desc, color=color)

    section_label(W // 2, modules_y - 22, "CORE MODULES")

    # Connectors: Flask → modules
    for i in range(len(modules)):
        mx = mx_start + i * (mw + gap) + mw // 2
        draw_arrow(draw, (fx + fw // 2, fy + fh), (mx, modules_y), width=1, head=8)

    # ── Data Storage ──────────────────────────────────────────────────────────
    store_y = 400
    stores = [
        (".work/{uuid}.json", "Session Work Files"),
        ("config.json", "Jira Credentials"),
        ("assignees.json", "User Cache"),
        ("labels.json", "Label Cache"),
        ("logs/", "App + Startup Logs"),
    ]
    sw, sh = 195, 65
    sx_start = 60
    sg = 32
    for i, (name, desc) in enumerate(stores):
        sx = sx_start + i * (sw + sg)
        box(sx, store_y, sw, sh, name, desc, color=BOX_TEAL, radius=8)

    section_label(W // 2, store_y - 22, "FILE STORAGE  (no database)")

    # Connectors: modules → storage
    draw_arrow(draw, (mx_start + 3 * (mw + gap) + mw // 2, modules_y + mh),
               (sx_start + sw // 2, store_y), width=1, head=8)
    draw_arrow(draw, (mx_start + 4 * (mw + gap) + mw // 2, modules_y + mh),
               (sx_start + sw + sg + sw // 2, store_y), width=1, head=8)

    # ── External: Jira Cloud ──────────────────────────────────────────────────
    jx, jy, jw, jh = 1150, 220, 190, 80
    box(jx, jy, jw, jh, "Jira Cloud", "REST API v3", color=BOX_ORG)
    section_label(jx + jw // 2, jy - 22, "EXTERNAL")

    # Connector: jira_client → Jira Cloud
    jira_mx = mx_start + 2 * (mw + gap) + mw
    draw_arrow(draw, (jira_mx, modules_y + mh // 2), (jx, jy + jh // 2), width=2, head=10)

    # ── External: LLM ─────────────────────────────────────────────────────────
    lx, ly, lw, lh = 1150, 108, 190, 70
    box(lx, ly, lw, lh, "LLM", "(Copilot / ChatGPT)", color=BOX_ORG)

    # Connector: browser → LLM (out-of-band, dashed appearance via dotted segments)
    draw.line([(bx + bw, by + bh // 2), (lx, ly + lh // 2)], fill=(200, 200, 200), width=2)
    draw.text((900, by + bh // 2 - 18), "copy prompt / paste output", font=f_sm, fill=(150, 150, 150))

    # Connector: Browser ↔ Flask
    draw_arrow(draw, (bx + bw, by + bh // 2), (fx, fy + fh // 2), width=2, head=10)
    draw_arrow(draw, (fx, fy + fh // 2 + 14), (bx + bw, by + bh // 2 + 14), width=2, head=10)

    # ── Start Scripts ─────────────────────────────────────────────────────────
    sx2, sy2, sw2, sh2 = 310, 540, 380, 65
    box(sx2, sy2, sw2, sh2, "start.sh / start.ps1",
        "venv · deps · CA cert merge · launch", color=(78, 52, 46), radius=8)
    section_label(sx2 + sw2 // 2, sy2 - 22, "LAUNCH SCRIPTS")
    draw_arrow(draw, (sx2 + sw2 // 2, sy2), (fx + fw // 2, fy + fh), width=1, head=8)

    # ── Legend ────────────────────────────────────────────────────────────────
    legend_items = [
        (BOX_BLUE,  "Flask / Routes / Jira Client"),
        (BOX_GRAY,  "Core Modules"),
        (BOX_TEAL,  "File Storage"),
        (BOX_ORG,   "External Services"),
        ((78,52,46),"Launch Scripts"),
    ]
    lx0, ly0 = 60, 680
    for i, (color, label) in enumerate(legend_items):
        cx = lx0 + i * 240
        draw_rounded_rect(draw, [cx, ly0, cx + 20, ly0 + 20], radius=4, fill=color)
        draw.text((cx + 28, ly0 + 2), label, font=f_sm, fill=TEXT_D)

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

    # ── Bottom row: storage & Jira Cloud ────────────────────────────────────
    mid_y = box_y + box_h + 60

    # Centre the two bottom boxes under the 4 steps
    total_bottom_w = 180 + 60 + 180   # work-file box + gap + jira box
    bottom_start_x = (W - total_bottom_w) // 2

    # Work file box (left of centre)
    wfx = bottom_start_x
    draw_rounded_rect(draw, [wfx, mid_y, wfx + 180, mid_y + 56],
                      radius=10, fill=BOX_TEAL, outline=None)
    centered_text(draw, wfx + 90, mid_y + 18, ".work/{uuid}.json", f_body, TEXT_W)
    centered_text(draw, wfx + 90, mid_y + 38, "Session storage", f_sm, TEXT_W)

    # Jira Cloud box (right of centre)
    jcx = bottom_start_x + 180 + 60
    draw_rounded_rect(draw, [jcx, mid_y, jcx + 180, mid_y + 56],
                      radius=10, fill=BOX_ORG, outline=None)
    centered_text(draw, jcx + 90, mid_y + 18, "Jira Cloud", f_body, TEXT_W)
    centered_text(draw, jcx + 90, mid_y + 38, "REST API v3", f_sm, TEXT_W)

    # Steps 2+3 → work file
    step2_cx = start_x + (box_w + gap) + box_w // 2
    step3_cx = start_x + 2 * (box_w + gap) + box_w // 2
    draw_arrow(draw, (step2_cx, box_y + box_h), (wfx + 90, mid_y), width=1, head=7)
    draw_arrow(draw, (step3_cx, box_y + box_h), (wfx + 90, mid_y), width=1, head=7)

    # Step 4 → Jira Cloud
    step4_cx = start_x + 3 * (box_w + gap) + box_w // 2
    draw_arrow(draw, (step4_cx, box_y + box_h), (jcx + 90, mid_y), width=2, head=10)

    # ── LLM note ─────────────────────────────────────────────────────────────
    draw.text((40, mid_y + 76), "* User copies prompt to their LLM (Copilot/ChatGPT), then pastes YAML output back into JiraMaster at Step 2",
              font=f_sm, fill=(120, 120, 120))

    img.save(os.path.join(OUT, "dataflow.png"), "PNG", dpi=(144, 144))
    print("✓ dataflow.png")


if __name__ == "__main__":
    diagram_architecture()
    diagram_dataflow()
    print("All diagrams generated in docs/images/")

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
# Layered swim-lane layout — arrows only travel straight down within each
# column so lines never cross.
#
# Layout (left → right columns, top → bottom rows):
#
#  Col 0 (Browser)   Col 1-8 (Flask + routes)          Col 9 (LLM — out-of-band)
#  ─────────────────────────────────────────────────────────────────────────────
#  [Browser]         [Flask App container]               [LLM / Copilot]
#       ↕ HTTP            ↓ (each route to module below)      ↑ copy/paste
#                    [Core Modules row]
#                    work_store  parser  prompt  models  jira_client  config  logging
#                         ↓        ↓                         ↓           ↓
#                    [.work/]  [cache/]                [Jira Cloud] [OS Keyring]
#                    [logs/]
#                    [config.json]
#
#  Bottom: [Launch Scripts] spanning full width, upward arrow to Flask
# ══════════════════════════════════════════════════════════════════════════════
def diagram_architecture():
    W, H = 1400, 900
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    f_title = load_font(24)
    f_head  = load_font(16)
    f_body  = load_font(13)
    f_sm    = load_font(12)
    f_xs    = load_font(11)

    # ── Helpers ───────────────────────────────────────────────────────────────
    def section_label(cx, y, label):
        w, _ = text_size(draw, label, f_xs)
        draw.text((cx - w // 2, y), label, font=f_xs, fill=(110, 110, 110))

    def box(x, y, w, h, title, subtitle=None, color=BOX_BLUE,
            text_color=TEXT_W, radius=10):
        draw_rounded_rect(draw, [x, y, x + w, y + h],
                          radius=radius, fill=color, outline=None)
        if subtitle:
            centered_text(draw, x + w // 2, y + h // 2 - 9, title,  f_body, text_color)
            centered_text(draw, x + w // 2, y + h // 2 + 9, subtitle, f_xs, text_color)
        else:
            centered_text(draw, x + w // 2, y + h // 2, title, f_body, text_color)

    def v_arrow(cx, y0, y1, color=ARROW, width=2, head=8):
        """Straight vertical arrow from (cx, y0) down to (cx, y1)."""
        draw_arrow(draw, (cx, y0), (cx, y1), color=color, width=width, head=head)

    # ─────────────────────────────────────────────────────────────────────────
    # ROW 0  — Title
    # ─────────────────────────────────────────────────────────────────────────
    centered_text(draw, W // 2, 30, "JiraMaster v3 — System Architecture", f_title, TEXT_D)

    # ─────────────────────────────────────────────────────────────────────────
    # ROW 1  — CLIENT (left) + Flask Application (centre) + LLM (right)
    #          y = 60 … 200
    # ─────────────────────────────────────────────────────────────────────────
    ROW1_Y = 62

    # Browser
    BW, BH = 130, 66
    BX = 30
    BY = ROW1_Y + 22
    box(BX, BY, BW, BH, "Browser", "(User)", color=(69, 90, 100))
    section_label(BX + BW // 2, ROW1_Y, "CLIENT")

    # Flask container
    FX, FY, FW, FH = 185, ROW1_Y, 960, 138
    draw_rounded_rect(draw, [FX, FY, FX + FW, FY + FH], radius=14,
                      fill=(236, 242, 255), outline=(30, 136, 229), width=2)
    centered_text(draw, FX + FW // 2, FY + 18, "Flask Application  (app.py)", f_head, BOX_BLUE)
    section_label(FX + FW // 2, FY - 18, "APPLICATION LAYER")

    # 8 route chips inside Flask  — fit evenly
    route_labels = ["/ home", "/prompt", "/import", "/edit",
                    "/upload", "/settings", "/tools", "/cache"]
    RW, RH = 108, 42
    r_gap = (FW - len(route_labels) * RW) // (len(route_labels) + 1)
    route_xs = [FX + r_gap + i * (RW + r_gap) for i in range(len(route_labels))]
    route_y = FY + 36
    for label, rx in zip(route_labels, route_xs):
        box(rx, route_y, RW, RH, label, color=BOX_BLUE, radius=6)

    # Security footer inside Flask
    sec_text = "CSRF · Security Headers · Session Fingerprinting · HttpOnly Cookies"
    sw, _ = text_size(draw, sec_text, f_xs)
    draw.text((FX + FW // 2 - sw // 2, FY + FH - 16),
              sec_text, font=f_xs, fill=(60, 100, 180))

    # Browser ↔ Flask  (horizontal bidirectional)
    mid_y = BY + BH // 2
    draw_arrow(draw, (BX + BW, mid_y - 5),  (FX, mid_y - 5),  width=2, head=9)
    draw_arrow(draw, (FX, mid_y + 9), (BX + BW, mid_y + 9), width=2, head=9)

    # LLM  (out-of-band, top-right)
    LLM_W, LLM_H = 175, 60
    LLM_X = W - LLM_W - 18
    LLM_Y = BY + (BH - LLM_H) // 2
    box(LLM_X, LLM_Y, LLM_W, LLM_H, "LLM", "(Copilot / ChatGPT)", color=BOX_ORG)
    section_label(LLM_X + LLM_W // 2, ROW1_Y, "OUT-OF-BAND")
    # Dashed horizontal line: Flask right edge → LLM left edge
    fx_right = FX + FW
    llm_mid_y = LLM_Y + LLM_H // 2
    dash_len, gap_len = 10, 6
    cx = fx_right + 4
    while cx + dash_len < LLM_X - 4:
        draw.line([(cx, llm_mid_y), (cx + dash_len, llm_mid_y)],
                  fill=(170, 170, 170), width=2)
        cx += dash_len + gap_len
    note_x = fx_right + 8
    draw.text((note_x, llm_mid_y - 16), "copy prompt /", font=f_xs, fill=(160, 160, 160))
    draw.text((note_x, llm_mid_y + 2),  "paste output",  font=f_xs, fill=(160, 160, 160))

    # ─────────────────────────────────────────────────────────────────────────
    # ROW 2  — Core Modules
    #          7 modules arranged so each sits in a named column.
    #          Columns are spaced to align with their downstream targets.
    #
    #  col index:  0          1         2         3          4            5         6
    #  module:   work_store  parser  prompt   models   jira_client   config   logging
    #  connects:  .work/     cache/   (none)   (none)   Jira Cloud  OS Keyring  logs/
    # ─────────────────────────────────────────────────────────────────────────
    ROW2_Y = 248
    MW, MH = 170, 66
    M_GAP = 22
    N_MOD = 7
    # centre the module row inside the Flask column range
    total_mod_w = N_MOD * MW + (N_MOD - 1) * M_GAP
    MX_START = FX + (FW - total_mod_w) // 2

    modules = [
        ("work_store.py",    "Session Store",   BOX_GRAY),  # → .work/  logs/
        ("parser.py",        "YAML → Epics",    BOX_GRAY),  # → cache/assignees
        ("prompt_builder.py","Prompt Gen",      BOX_GRAY),  # (no storage)
        ("models.py",        "Dataclasses",     BOX_GRAY),  # (no storage)
        ("jira_client.py",   "Jira REST v3",    BOX_BLUE),  # → Jira Cloud
        ("config.py",        "Config+Keyring",  BOX_GRAY),  # → config.json / OS Keyring
        ("logging_config.py","Centralised Logs",BOX_GRAY),  # (log files via work_store)
    ]
    mod_centers = []
    for i, (name, desc, color) in enumerate(modules):
        mx = MX_START + i * (MW + M_GAP)
        box(mx, ROW2_Y, MW, MH, name, desc, color=color)
        mod_centers.append(mx + MW // 2)

    section_label(FX + FW // 2, ROW2_Y - 20, "CORE MODULES")

    # Flask → each module  (straight vertical — each route chip roughly above
    # the module strip; use the module centre x, from Flask bottom)
    flask_bottom = FY + FH
    for cx in mod_centers:
        v_arrow(cx, flask_bottom, ROW2_Y, width=1, head=6)

    # ─────────────────────────────────────────────────────────────────────────
    # ROW 3  — Split into two groups separated by a gap
    #
    #  LEFT  (under modules 0-3):  File Storage  (4 boxes)
    #  RIGHT (under modules 4-5):  External Services  (3 boxes, stacked)
    # ─────────────────────────────────────────────────────────────────────────
    ROW3_Y = 382

    # ── File Storage (left group, under work_store / parser / prompt / models)
    LEFT_COL_END = MX_START + 3 * (MW + M_GAP) + MW  # right edge of models.py

    stores = [
        (".work/{uuid}.json", "Session Work Files"),
        ("cache/",            "Assignee / Label / Project"),
        ("config.json",       "Jira Credentials"),
        ("logs/",             "App + Startup Logs"),
    ]
    n_stores = len(stores)
    LEFT_STORE_W = LEFT_COL_END - MX_START
    SW = (LEFT_STORE_W - (n_stores - 1) * 14) // n_stores
    SH = 60
    s_gap = 14
    store_xs = [MX_START + i * (SW + s_gap) for i in range(n_stores)]
    store_centers = [sx + SW // 2 for sx in store_xs]

    for sx, (name, desc) in zip(store_xs, stores):
        box(sx, ROW3_Y, SW, SH, name, desc, color=BOX_TEAL, radius=8)
    section_label(MX_START + LEFT_STORE_W // 2, ROW3_Y - 20,
                  "FILE STORAGE  (no database)")

    # Module → storage arrows (straight vertical)
    # work_store.py → .work/
    v_arrow(store_centers[0], ROW2_Y + MH, ROW3_Y, width=1, head=7)
    # parser.py → cache/
    v_arrow(store_centers[1], ROW2_Y + MH, ROW3_Y, width=1, head=7)
    # config.py → config.json
    v_arrow(store_centers[2], ROW2_Y + MH, ROW3_Y, width=1, head=7)
    # logging_config.py → logs/
    v_arrow(store_centers[3], ROW2_Y + MH, ROW3_Y, width=1, head=7)

    # ── External Services — each in its own column under the module that uses it
    # jira_client.py (mod 4) → Jira Cloud + Atlassian Teams (side by side)
    # config.py      (mod 5) → OS Keyring
    EH, E_GAP = 60, 14

    # Jira Cloud — centred under jira_client.py
    jc_cx = mod_centers[4]
    EW_JC = MW + 20
    jc_x  = jc_cx - EW_JC // 2
    box(jc_x, ROW3_Y, EW_JC, EH, "Jira Cloud", "REST API v3", color=BOX_ORG)
    v_arrow(jc_cx, ROW2_Y + MH, ROW3_Y, width=2, head=10)

    # Atlassian Teams — to the right of Jira Cloud, connected by a thin arrow
    # from jira_client as well (offset slightly right)
    at_x = jc_x + EW_JC + E_GAP
    EW_AT = MW
    box(at_x, ROW3_Y, EW_AT, EH, "Atlassian Teams", "Teams API", color=BOX_ORG)
    at_cx = at_x + EW_AT // 2
    v_arrow(at_cx, ROW2_Y + MH, ROW3_Y, width=1, head=7)

    # OS Keyring — centred under config.py
    cfg_cx = mod_centers[5]
    EW_KR = MW + 10
    kr_x  = cfg_cx - EW_KR // 2
    box(kr_x, ROW3_Y, EW_KR, EH, "OS Keyring", "macOS / Windows", color=BOX_ORG)
    v_arrow(cfg_cx, ROW2_Y + MH, ROW3_Y, width=1, head=7)

    # Section label centred over all three external boxes
    ext_left  = jc_x
    ext_right = kr_x + EW_KR
    section_label((ext_left + ext_right) // 2, ROW3_Y - 20, "EXTERNAL SERVICES")

    # ─────────────────────────────────────────────────────────────────────────
    # ROW 4  — Launch Scripts (bottom banner, outside the data-flow)
    #  Arrow routed up the LEFT edge of the Flask column to avoid crossing
    #  the module and storage rows.
    # ─────────────────────────────────────────────────────────────────────────
    ROW4_Y = 610
    LSW = FW
    LSH = 56
    LSX = FX
    box(LSX, ROW4_Y, LSW, LSH,
        "start.sh  /  start.ps1  /  start.bat",
        "venv · pip install · CA cert merge · launch Flask",
        color=(78, 52, 46), radius=8)
    section_label(LSX + LSW // 2, ROW4_Y - 18, "LAUNCH SCRIPTS")
    # Route the launch arrow up the left margin — clear of all module/storage boxes.
    # Three segments: horizontal left → vertical up → horizontal right into Flask.
    LS_COLOR  = (78, 52, 46)
    MARGIN_X  = LSX - 30   # left of everything
    ls_top_y  = ROW4_Y     # top of scripts banner
    ls_mid_y  = ls_top_y + LSH // 2
    # 1. Horizontal: scripts left edge → margin
    draw.line([(LSX, ls_mid_y), (MARGIN_X, ls_mid_y)], fill=LS_COLOR, width=2)
    # 2. Vertical: margin bottom → margin at Flask bottom
    draw.line([(MARGIN_X, ls_mid_y), (MARGIN_X, flask_bottom)], fill=LS_COLOR, width=2)
    # 3. Horizontal + arrowhead: margin → Flask left edge
    draw_arrow(draw, (MARGIN_X, flask_bottom), (FX, flask_bottom),
               color=LS_COLOR, width=2, head=9)

    # ─────────────────────────────────────────────────────────────────────────
    # Legend
    # ─────────────────────────────────────────────────────────────────────────
    legend_items = [
        (BOX_BLUE,      "Flask / Routes / Jira Client"),
        (BOX_GRAY,      "Core Modules"),
        (BOX_TEAL,      "File Storage"),
        (BOX_ORG,       "External Services"),
        ((78, 52, 46),  "Launch Scripts"),
    ]
    LG_X, LG_Y = 30, 820
    for i, (color, label) in enumerate(legend_items):
        lx = LG_X + i * 250
        draw_rounded_rect(draw, [lx, LG_Y, lx + 18, LG_Y + 18], radius=3, fill=color)
        draw.text((lx + 26, LG_Y + 1), label, font=f_xs, fill=TEXT_D)

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

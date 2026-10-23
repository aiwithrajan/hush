import math
from PIL import Image, ImageDraw, ImageFont

W, H = 1200, 630
img = Image.new("RGBA", (W, H), (9, 13, 22, 255))
draw = ImageDraw.Draw(img)

# Background subtle radial gradient / grid glow
for y in range(H):
    for x in range(0, W, 40):
        pass

# Draw glowing ambient background circles
def draw_glow(x0, y0, radius, color):
    for r in range(radius, 0, -5):
        alpha = int((1 - r / radius) ** 2 * color[3])
        draw.ellipse([x0 - r, y0 - r, x0 + r, y0 + r], fill=(color[0], color[1], color[2], alpha))

# Ambient glowing circles
draw_glow(200, 180, 260, (16, 185, 129, 35))   # Emerald glow top-left
draw_glow(950, 400, 300, (6, 182, 212, 30))   # Cyan glow bottom-right
draw_glow(600, 600, 250, (99, 102, 241, 25))  # Indigo glow bottom

# Subtle grid lines
for x in range(0, W, 60):
    draw.line([(x, 0), (x, H)], fill=(255, 255, 255, 6), width=1)
for y in range(0, H, 60):
    draw.line([(0, y), (W, y)], fill=(255, 255, 255, 6), width=1)

# Fonts
font_title = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 64)
font_subtitle = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 26)
font_body = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 18)
font_tag = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 13)
font_code_bold = ImageFont.truetype("/System/Library/Fonts/SFNSMono.ttf", 13)
font_code = ImageFont.truetype("/System/Library/Fonts/SFNSMono.ttf", 12)

# --- LEFT COLUMN: Brand & Messaging ---
# Top Badge
bx0, by0, bx1, by1 = 60, 65, 395, 95
draw.rounded_rectangle([bx0, by0, bx1, by1], radius=8, fill=(16, 185, 129, 30), outline=(16, 185, 129, 100), width=1)
draw.text((bx0 + 16, by0 + 8), "HACKTOBERFEST AI CHALLENGE · WEEK 3", fill=(52, 211, 153), font=font_tag)

# Title & Subtitle
draw.text((60, 120), "HUSH", fill=(255, 255, 255), font=font_title)
# Emerald dot on Hush
draw.ellipse([270, 160, 286, 176], fill=(16, 185, 129))

draw.text((60, 205), "The Local Attention Operating System", fill=(226, 232, 240), font=font_subtitle)
draw.text((60, 248), "Reads every notification locally so you only read four.", fill=(148, 163, 184), font=font_body)
draw.text((60, 276), "10 staged emergencies caught with 100% precision.", fill=(148, 163, 184), font=font_body)

# Feature Badges Pill Boxes
badges = [
    ("🧠 Gemma 2B (On-Device)", (99, 102, 241)),
    ("⏳ Temporal Durable Timers", (6, 182, 212)),
    ("🔒 Zero Cloud Data Leakage", (16, 185, 129)),
    ("🎯 100% Emergency Recall", (245, 158, 11)),
]

badge_y = 330
for text, color in badges:
    draw.rounded_rectangle([60, badge_y, 440, badge_y + 38], radius=8, fill=(15, 23, 42, 220), outline=(color[0], color[1], color[2], 120), width=1)
    # colored indicator dot
    draw.ellipse([75, badge_y + 14, 85, badge_y + 24], fill=color)
    draw.text((95, badge_y + 10), text, fill=(241, 245, 249), font=font_tag)
    badge_y += 48

# Bottom CTA pill
draw.rounded_rectangle([60, 535, 300, 575], radius=8, fill=(16, 185, 129, 230))
draw.text((80, 546), "LIVE DEMO + CODE + FIRE DRILL", fill=(9, 13, 22), font=font_tag)

# --- RIGHT COLUMN: The 4-Line Brief Terminal Card ---
cx0, cy0, cx1, cy1 = 510, 65, 1140, 575

# Card Shadow / Outer border
draw.rounded_rectangle([cx0 - 2, cy0 - 2, cx1 + 2, cy1 + 2], radius=16, fill=(30, 41, 59, 100), outline=(51, 65, 85, 180), width=1)
draw.rounded_rectangle([cx0, cy0, cx1, cy1], radius=16, fill=(11, 15, 25, 240))

# Window header bar
draw.rounded_rectangle([cx0, cy0, cx1, cy0 + 44], radius=16, fill=(19, 26, 42, 255))
draw.rectangle([cx0, cy0 + 25, cx1, cy0 + 44], fill=(19, 26, 42, 255)) # square bottom of header
draw.line([(cx0, cy0 + 44), (cx1, cy0 + 44)], fill=(51, 65, 85, 180), width=1)

# macOS traffic lights
draw.ellipse([cx0 + 16, cy0 + 16, cx0 + 28, cy0 + 28], fill=(239, 68, 68))
draw.ellipse([cx0 + 36, cy0 + 16, cx0 + 48, cy0 + 28], fill=(245, 158, 11))
draw.ellipse([cx0 + 56, cy0 + 16, cx0 + 68, cy0 + 28], fill=(16, 185, 129))

draw.text((cx0 + 90, cy0 + 15), "hush — 4-Line Brief Router (Temporal Cadence)", fill=(148, 163, 184), font=font_code)
# Green Live Status Dot
draw.ellipse([cx1 - 85, cy0 + 18, cx1 - 77, cy0 + 26], fill=(16, 185, 129))
draw.text((cx1 - 70, cy0 + 15), "ACTIVE", fill=(16, 185, 129), font=font_tag)

# Card Content: Cadence Window Header
draw.text((cx0 + 24, cy0 + 64), "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", fill=(51, 65, 85), font=font_code)
draw.text((cx0 + 24, cy0 + 82), "H U S H   B R I E F   ·   2026-10-23 09:30 – 12:30", fill=(52, 211, 153), font=font_code_bold)
draw.text((cx0 + 24, cy0 + 100), "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", fill=(51, 65, 85), font=font_code)

# The 4 Kept Lines
brief_lines = [
    ("1.", "[FAMILY]", "WA ", "Sister: Car broke down on Hwy 101, engine smoking...", "HIGH URGENCY", (239, 68, 68)),
    ("2.", "[HEALTH]", "SMS", "City Hospital ER: Father admitted to Room 4...", "CRITICAL", (239, 68, 68)),
    ("3.", "[FRAUD ]", "SMS", "Chase: Suspicious debit $2,400 in Frankfurt...", "ACTION REQ", (245, 158, 11)),
    ("4.", "[OUTAGE]", "SLK", "DevOps: Kubernetes prod-db primary failover...", "SEV-1 ALERT", (245, 158, 11)),
]

line_y = cy0 + 126
for num, cat, src, msg, tag_text, tag_col in brief_lines:
    # row background
    draw.rounded_rectangle([cx0 + 20, line_y, cx1 - 20, line_y + 44], radius=6, fill=(15, 23, 42, 160), outline=(30, 41, 59, 120), width=1)
    draw.text((cx0 + 32, line_y + 14), num, fill=(148, 163, 184), font=font_code_bold)
    draw.text((cx0 + 55, line_y + 14), cat, fill=(99, 102, 241), font=font_code_bold)
    draw.text((cx0 + 130, line_y + 14), src, fill=(56, 189, 248), font=font_code_bold)
    draw.text((cx0 + 175, line_y + 14), msg, fill=(241, 245, 249), font=font_code)
    # tag badge
    draw.rounded_rectangle([cx1 - 135, line_y + 10, cx1 - 30, line_y + 34], radius=4, fill=(tag_col[0], tag_col[1], tag_col[2], 35), outline=(tag_col[0], tag_col[1], tag_col[2], 120), width=1)
    draw.text((cx1 - 127, line_y + 15), tag_text, fill=tag_col, font=font_tag)
    line_y += 52

# Summary bar
draw.text((cx0 + 24, line_y + 5), "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", fill=(51, 65, 85), font=font_code)
draw.text((cx0 + 24, line_y + 24), "43 notifications cut into Discard Pile  ·  Next brief in 2h 58m", fill=(148, 163, 184), font=font_code)

# Fire Drill Confusion Matrix Scorecard Box
box_y = line_y + 56
draw.rounded_rectangle([cx0 + 20, box_y, cx1 - 20, cy1 - 20], radius=8, fill=(16, 24, 39, 230), outline=(16, 185, 129, 80), width=1)

draw.text((cx0 + 36, box_y + 12), "FIRE DRILL BENCHMARK SCORECARD", fill=(52, 211, 153), font=font_tag)

metrics = [
    ("RECALL", "100.0%", "10/10 Caught", (16, 185, 129)),
    ("PRECISION", "100.0%", "0 False Alarms", (16, 185, 129)),
    ("SILENCE", "100.0%", "5/5 Controls Cut", (16, 185, 129)),
    ("AVG LATENCY", "3.99s", "Local Gemma 2B", (56, 189, 248)),
]

col_w = (cx1 - cx0 - 60) // 4
for i, (m_label, m_val, m_sub, m_col) in enumerate(metrics):
    mx = cx0 + 36 + i * col_w
    draw.text((mx, box_y + 36), m_label, fill=(148, 163, 184), font=font_tag)
    draw.text((mx, box_y + 52), m_val, fill=m_col, font=font_subtitle)
    draw.text((mx, box_y + 82), m_sub, fill=(100, 116, 139), font=font_code)

# Convert RGBA to RGB for saving as high quality PNG
final_img = Image.new("RGB", (W, H), (9, 13, 22))
final_img.paste(img, mask=img.split()[3])
final_img.save("/Users/apple/Desktop/hack4/hush_cover.png", "PNG", quality=95)
print("Successfully generated /Users/apple/Desktop/hack4/hush_cover.png (1200x630)")

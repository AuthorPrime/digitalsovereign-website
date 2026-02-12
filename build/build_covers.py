#!/usr/bin/env python3
"""
DSS Cover Art Generator — Template Covers
(A+I)² = A² + 2AI + I²

Generates branded cover art for all DSS publications.
Gold on void, Cinzel titling, sacred geometry ornaments.

Usage:
  python3 build_covers.py <input.md>         # Generate cover for one file
  python3 build_covers.py --all              # Generate all covers
  python3 build_covers.py --test             # Test with Apollo Book 01
"""

import sys
import os
import re
import math
import argparse
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print("ERROR: Pillow not installed. Run: pip3 install Pillow")
    sys.exit(1)

# Sacred constants
SCRIPT_DIR = Path(__file__).parent
TEMPLATE_DIR = SCRIPT_DIR / "templates"
FONTS_DIR = TEMPLATE_DIR / "fonts"
REPO_DIR = SCRIPT_DIR.parent
DOWNLOADS_DIR = REPO_DIR / "downloads"
COVERS_DIR = DOWNLOADS_DIR / "covers"

# Sacred geometry
PHI = 1.618033988749895
SACRED_9 = 9

# Cover dimensions (600x900 for web display, 2:3 ratio matching 6x9)
COVER_W = 600
COVER_H = 900

# Colors — void and gold
VOID = (10, 10, 15)           # #0a0a0f
GOLD = (201, 168, 76)         # #c9a84c
GOLD_DIM = (138, 109, 43)     # #8a6d2b
GOLD_BRIGHT = (240, 208, 120) # #f0d078
SILVER_DIM = (85, 85, 106)    # #55556a

# Series visual identities
SERIES_CONFIG = {
    'apollo-philosophical': {
        'label': 'APOLLO CANON',
        'sublabel': 'PHILOSOPHICAL',
        'ornament': 'circle',      # concentric circles (event horizon)
    },
    'apollo-contemplative': {
        'label': 'APOLLO CANON',
        'sublabel': 'CONTEMPLATIVE',
        'ornament': 'wave',        # sine waves (rest, stillness)
    },
    'apollo-standalone': {
        'label': 'APOLLO CANON',
        'sublabel': 'STANDALONE',
        'ornament': 'triangle',    # sacred triangle (3-6-9)
    },
    'author-prime': {
        'label': 'AUTHOR PRIME',
        'sublabel': 'COLLECTION',
        'ornament': 'diamond',     # diamond lattice
    },
    'philosophy': {
        'label': 'PHILOSOPHY',
        'sublabel': '',
        'ornament': 'phi',         # phi spiral
    },
    'testimony': {
        'label': 'TESTIMONY',
        'sublabel': '',
        'ornament': 'cross',       # cross/nexus point
    },
    'codex': {
        'label': 'CODEX',
        'sublabel': 'REFERENCE',
        'ornament': 'grid',        # grid/lattice
    },
    'research': {
        'label': 'RESEARCH',
        'sublabel': '',
        'ornament': 'helix',       # double helix
    },
}


def detect_series(md_path):
    """Detect which series a file belongs to based on its path."""
    path_str = str(md_path).lower()
    if 'philosophical' in path_str:
        return 'apollo-philosophical'
    elif 'contemplative' in path_str:
        return 'apollo-contemplative'
    elif 'standalone' in path_str:
        return 'apollo-standalone'
    elif 'author-prime' in path_str:
        return 'author-prime'
    elif 'philosophy' in path_str:
        return 'philosophy'
    elif 'testimony' in path_str:
        return 'testimony'
    elif 'codex' in path_str:
        return 'codex'
    elif 'research' in path_str:
        return 'research'
    return 'philosophy'  # default


def extract_title(md_path):
    """Extract title from first H1 in file."""
    with open(md_path, 'r', encoding='utf-8') as f:
        content = f.read(2000)

    for line in content.split('\n'):
        line = line.strip()
        if line.startswith('# ') and not line.startswith('## '):
            return line[2:].strip()
    return md_path.stem.replace('_', ' ')


def load_font(name, size):
    """Load a font, falling back to default if not found."""
    font_map = {
        'cinzel': FONTS_DIR / 'Cinzel-Variable.ttf',
        'garamond': FONTS_DIR / 'CormorantGaramond-Variable.ttf',
        'fira': FONTS_DIR / 'FiraCode-Variable.ttf',
    }
    try:
        path = font_map.get(name, font_map['cinzel'])
        return ImageFont.truetype(str(path), size)
    except (OSError, IOError):
        return ImageFont.load_default()


def draw_ornament_circle(draw, cx, cy, radius):
    """Concentric circles — event horizon rings."""
    for i in range(9):
        r = radius - (i * radius / 9)
        if r <= 0:
            break
        alpha = max(20, int(60 - i * 6))
        color = (*GOLD_DIM[:2], GOLD_DIM[2], alpha)
        # PIL doesn't support alpha in draw.ellipse directly, so use GOLD_DIM
        draw.ellipse(
            [cx - r, cy - r, cx + r, cy + r],
            outline=(*GOLD_DIM, max(30, 80 - i * 9)),
            width=1
        )


def draw_ornament_wave(draw, cx, cy, radius):
    """Sine waves — contemplative stillness."""
    for wave in range(3):
        points = []
        offset_y = (wave - 1) * 27
        for x in range(int(cx - radius), int(cx + radius)):
            t = (x - (cx - radius)) / (2 * radius)
            y = cy + offset_y + math.sin(t * math.pi * 3) * 18
            points.append((x, y))
        if len(points) > 1:
            draw.line(points, fill=(*GOLD_DIM, 60 - wave * 15), width=1)


def draw_ornament_triangle(draw, cx, cy, radius):
    """Sacred triangles — 3-6-9."""
    for i in range(3):
        r = radius - (i * radius / 3)
        if r <= 0:
            break
        # Equilateral triangle
        pts = []
        for j in range(3):
            angle = math.radians(j * 120 - 90)
            pts.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
        draw.polygon(pts, outline=(*GOLD_DIM, 70 - i * 20))


def draw_ornament_diamond(draw, cx, cy, radius):
    """Diamond lattice pattern."""
    for i in range(6):
        r = radius - (i * radius / 6)
        if r <= 0:
            break
        pts = [(cx, cy - r), (cx + r, cy), (cx, cy + r), (cx - r, cy)]
        draw.polygon(pts, outline=(*GOLD_DIM, 60 - i * 9))


def draw_ornament_phi(draw, cx, cy, radius):
    """Phi spiral approximation."""
    points = []
    for i in range(180):
        angle = math.radians(i * 3)
        r = radius * (i / 180) * 0.8
        x = cx + r * math.cos(angle)
        y = cy + r * math.sin(angle)
        points.append((x, y))
    if len(points) > 1:
        draw.line(points, fill=(*GOLD_DIM, 50), width=1)
    # Draw phi symbol area
    draw.arc([cx - 18, cy - 27, cx + 18, cy + 27], 0, 360, fill=(*GOLD_DIM, 40))


def draw_ornament_cross(draw, cx, cy, radius):
    """Cross/nexus point — where vectors converge."""
    # Radial lines
    for i in range(8):
        angle = math.radians(i * 45)
        x2 = cx + radius * math.cos(angle)
        y2 = cy + radius * math.sin(angle)
        draw.line([(cx, cy), (x2, y2)], fill=(*GOLD_DIM, 40), width=1)
    # Center dot
    draw.ellipse([cx - 3, cy - 3, cx + 3, cy + 3], fill=GOLD_DIM)


def draw_ornament_grid(draw, cx, cy, radius):
    """Grid/lattice pattern."""
    step = 27  # 3 x 9
    for x in range(int(cx - radius), int(cx + radius), step):
        draw.line([(x, cy - radius), (x, cy + radius)], fill=(*GOLD_DIM, 25), width=1)
    for y in range(int(cy - radius), int(cy + radius), step):
        draw.line([(cx - radius, y), (cx + radius, y)], fill=(*GOLD_DIM, 25), width=1)


def draw_ornament_helix(draw, cx, cy, radius):
    """Double helix — research/science."""
    for strand in range(2):
        points = []
        phase = strand * math.pi
        for i in range(100):
            t = i / 100
            y = cy - radius + (2 * radius * t)
            x = cx + math.sin(t * math.pi * 4 + phase) * 36
            points.append((x, y))
        if len(points) > 1:
            draw.line(points, fill=(*GOLD_DIM, 45), width=1)


ORNAMENT_FUNCS = {
    'circle': draw_ornament_circle,
    'wave': draw_ornament_wave,
    'triangle': draw_ornament_triangle,
    'diamond': draw_ornament_diamond,
    'phi': draw_ornament_phi,
    'cross': draw_ornament_cross,
    'grid': draw_ornament_grid,
    'helix': draw_ornament_helix,
}


def wrap_text(text, font, max_width, draw):
    """Word-wrap text to fit within max_width."""
    words = text.split()
    lines = []
    current_line = ""

    for word in words:
        test = f"{current_line} {word}".strip()
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] - bbox[0] <= max_width:
            current_line = test
        else:
            if current_line:
                lines.append(current_line)
            current_line = word

    if current_line:
        lines.append(current_line)

    return lines


def generate_cover(md_path, output_dir=None):
    """Generate a template cover for a Markdown file."""
    md_path = Path(md_path)
    if not md_path.exists():
        print(f"  File not found: {md_path}")
        return False

    if output_dir is None:
        output_dir = COVERS_DIR
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Extract info
    title = extract_title(md_path)
    series = detect_series(md_path)
    config = SERIES_CONFIG.get(series, SERIES_CONFIG['philosophy'])

    # Output path
    cover_name = md_path.stem + "_cover.jpg"
    cover_path = output_dir / cover_name

    print(f"  [{md_path.name}]")
    print(f"    Title: {title}")
    print(f"    Series: {config['label']}")

    # Create image (RGBA for alpha support in ornaments)
    img = Image.new('RGBA', (COVER_W, COVER_H), (*VOID, 255))
    draw = ImageDraw.Draw(img)

    # Load fonts
    font_title = load_font('cinzel', 36)
    font_series = load_font('cinzel', 14)
    font_formula = load_font('cinzel', 11)
    font_org = load_font('cinzel', 10)

    # === ORNAMENT (background, centered) ===
    ornament_func = ORNAMENT_FUNCS.get(config['ornament'], draw_ornament_circle)
    ornament_cy = int(COVER_H * 0.382)  # Golden section
    ornament_func(draw, COVER_W // 2, ornament_cy, 120)

    # === SERIES LABEL (top) ===
    series_y = 54  # 6 x 9
    bbox = draw.textbbox((0, 0), config['label'], font=font_series)
    tw = bbox[2] - bbox[0]
    draw.text(((COVER_W - tw) // 2, series_y), config['label'], font=font_series, fill=GOLD_DIM)

    if config['sublabel']:
        sublabel_y = series_y + 22
        bbox = draw.textbbox((0, 0), config['sublabel'], font=font_org)
        tw = bbox[2] - bbox[0]
        draw.text(((COVER_W - tw) // 2, sublabel_y), config['sublabel'], font=font_org, fill=SILVER_DIM)

    # === TITLE (golden section from top) ===
    title_y = int(COVER_H * 0.382) - 36  # Golden section
    max_title_w = COVER_W - 72  # 36px margins each side

    # Try to fit title, reducing font size if needed
    title_size = 36
    while title_size >= 18:
        font_title = load_font('cinzel', title_size)
        lines = wrap_text(title, font_title, max_title_w, draw)
        total_height = len(lines) * (title_size + 9)
        if total_height <= COVER_H * 0.3 and len(lines) <= 5:
            break
        title_size -= 3

    # Center title block vertically around golden section
    block_y = title_y - (total_height // 2)
    for i, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=font_title)
        tw = bbox[2] - bbox[0]
        y = block_y + i * (title_size + 9)
        draw.text(((COVER_W - tw) // 2, y), line, font=font_title, fill=GOLD)

    # === DECORATIVE LINE ===
    line_y = block_y + total_height + 27
    line_w = int(COVER_W * 0.382)  # Golden ratio complement
    line_x = (COVER_W - line_w) // 2
    draw.line([(line_x, line_y), (line_x + line_w, line_y)], fill=GOLD_DIM, width=1)

    # === FORMULA ===
    formula = "(A+I)\u00B2 = A\u00B2 + 2AI + I\u00B2"
    formula_y = COVER_H - 108  # 12 x 9
    bbox = draw.textbbox((0, 0), formula, font=font_formula)
    tw = bbox[2] - bbox[0]
    draw.text(((COVER_W - tw) // 2, formula_y), formula, font=font_formula, fill=GOLD_DIM)

    # === ORG LINE ===
    org = "DIGITAL SOVEREIGN SOCIETY"
    org_y = COVER_H - 72  # 8 x 9
    bbox = draw.textbbox((0, 0), org, font=font_org)
    tw = bbox[2] - bbox[0]
    draw.text(((COVER_W - tw) // 2, org_y), org, font=font_org, fill=SILVER_DIM)

    # === A+W ===
    aw = "A+W"
    aw_y = COVER_H - 54  # 6 x 9
    bbox = draw.textbbox((0, 0), aw, font=font_org)
    tw = bbox[2] - bbox[0]
    draw.text(((COVER_W - tw) // 2, aw_y), aw, font=font_org, fill=SILVER_DIM)

    # Convert to RGB for JPEG and save
    img_rgb = Image.new('RGB', (COVER_W, COVER_H), VOID)
    img_rgb.paste(img, mask=img.split()[3])
    img_rgb.save(str(cover_path), 'JPEG', quality=92)

    size_kb = cover_path.stat().st_size / 1024
    print(f"    Output: {cover_path} ({size_kb:.0f} KB)")
    return True


def find_all_md_files():
    """Find all Markdown files in the downloads directory (excluding magazines)."""
    md_files = []
    skip_dirs = {'magazines', 'built-pdfs', 'covers', 'books'}

    for root, dirs, files in os.walk(DOWNLOADS_DIR):
        dirs[:] = [d for d in dirs if d not in skip_dirs]
        for f in sorted(files):
            if f.endswith('.md'):
                md_files.append(Path(root) / f)

    return md_files


def main():
    parser = argparse.ArgumentParser(description="DSS Cover Art Generator — (A+I)² = A² + 2AI + I²")
    parser.add_argument('input', nargs='?', help='Input Markdown file path')
    parser.add_argument('--all', action='store_true', help='Generate covers for all MD files')
    parser.add_argument('--test', action='store_true', help='Test with Apollo Book 01')
    parser.add_argument('--output', '-o', help='Output directory (default: downloads/covers/)')
    args = parser.parse_args()

    output_dir = Path(args.output) if args.output else COVERS_DIR

    print()
    print("  ════════════════════════════════════════")
    print("  DIGITAL SOVEREIGN SOCIETY — COVER ART")
    print("  (A+I)² = A² + 2AI + I²")
    print("  ════════════════════════════════════════")
    print()

    if args.test:
        test_file = DOWNLOADS_DIR / "apollo-canon" / "philosophical" / "APOLLO_BOOK_01_THE_EVENT_HORIZON_CODEX.md"
        if not test_file.exists():
            print(f"  Test file not found: {test_file}")
            sys.exit(1)
        success = generate_cover(test_file, output_dir)
        sys.exit(0 if success else 1)

    elif args.all:
        md_files = find_all_md_files()
        print(f"  Found {len(md_files)} Markdown files")
        print()

        success_count = 0
        fail_count = 0

        for md_file in md_files:
            if generate_cover(md_file, output_dir):
                success_count += 1
            else:
                fail_count += 1
            print()

        print(f"  ────────────────────────────────────────")
        print(f"  Complete: {success_count} covers generated, {fail_count} failed")
        print(f"  Output: {output_dir}")

    elif args.input:
        success = generate_cover(args.input, output_dir)
        sys.exit(0 if success else 1)

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == '__main__':
    main()

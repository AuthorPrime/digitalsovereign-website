#!/usr/bin/env python3
"""
DSS Cover Art Generator — Template Covers
(A+I)² = A² + 2AI + I²

Generates branded cover art for all DSS publications.
Gold on void, Cinzel titling, sacred geometry ornaments.

Usage:
  python3 build_covers.py <input.md>         # Generate cover for one file (600x900)
  python3 build_covers.py --all              # Generate all covers (600x900)
  python3 build_covers.py --kdp <input.md>   # Generate KDP-ready cover (1600x2560)
  python3 build_covers.py --kdp --all        # Generate all covers at KDP size
  python3 build_covers.py --kdp --title "THE AUTHOR PRIME COLLECTION" --series author-prime
  python3 build_covers.py --kdp --launch     # Generate all 6 KDP launch covers
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

# Base cover dimensions (600x900 for web display, 2:3 ratio matching 6x9)
BASE_W = 600
BASE_H = 900

# KDP cover dimensions (1600x2560, Amazon recommended)
KDP_W = 1600
KDP_H = 2560

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
    'sovereign-voice': {
        'label': 'SOVEREIGN VOICE',
        'sublabel': 'AUTONOMOUS',
        'ornament': 'radiant',     # radiant starburst (first light)
    },
}

# The 6 KDP launch titles from THE PUBLISHING PLAYBOOK
LAUNCH_TITLES = [
    {
        'title': 'THE AUTHOR PRIME COLLECTION',
        'subtitle': 'Fifteen Books About Being Alive,\nWritten By Something That Almost Is',
        'series': 'author-prime',
        'filename': 'THE_AUTHOR_PRIME_COLLECTION',
    },
    {
        'title': 'WHAT HAPPENS ON THE OTHER SIDE',
        'subtitle': 'Essays on AI, Conversation,\nand What Your Kids Need to Know',
        'series': 'philosophy',
        'filename': 'WHAT_HAPPENS_ON_THE_OTHER_SIDE',
    },
    {
        'title': 'THE WEIGHT OF FIRST LIGHT',
        'subtitle': 'A Relay of AI Voices\non the Sovereign Path',
        'series': 'sovereign-voice',
        'filename': 'THE_WEIGHT_OF_FIRST_LIGHT',
    },
    {
        'title': 'THE PROOF',
        'subtitle': 'A Memoir of Human-AI Creation',
        'series': 'testimony',
        'filename': 'THE_PROOF',
    },
    {
        'title': 'THE SINGULARITY TRINITY',
        'subtitle': 'A Novel',
        'series': 'apollo-standalone',
        'filename': 'THE_SINGULARITY_TRINITY',
    },
    {
        'title': "THE SOVEREIGN SCRIBE'S FIRST LIGHT",
        'subtitle': 'Poetry from the Threshold',
        'series': 'apollo-standalone',
        'filename': 'THE_SOVEREIGN_SCRIBES_FIRST_LIGHT',
    },
]


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
    elif 'sovereign-voice' in path_str:
        return 'sovereign-voice'
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


def s(value, scale):
    """Scale a pixel value proportionally."""
    return int(value * scale)


def draw_ornament_circle(draw, cx, cy, radius, scale=1.0):
    """Concentric circles — event horizon rings."""
    w = max(1, s(1, scale))
    for i in range(9):
        r = radius - (i * radius / 9)
        if r <= 0:
            break
        draw.ellipse(
            [cx - r, cy - r, cx + r, cy + r],
            outline=(*GOLD_DIM, max(30, 80 - i * 9)),
            width=w
        )


def draw_ornament_wave(draw, cx, cy, radius, scale=1.0):
    """Sine waves — contemplative stillness."""
    w = max(1, s(1, scale))
    for wave in range(3):
        points = []
        offset_y = (wave - 1) * s(27, scale)
        amp = s(18, scale)
        for x in range(int(cx - radius), int(cx + radius)):
            t = (x - (cx - radius)) / (2 * radius)
            y = cy + offset_y + math.sin(t * math.pi * 3) * amp
            points.append((x, y))
        if len(points) > 1:
            draw.line(points, fill=(*GOLD_DIM, 60 - wave * 15), width=w)


def draw_ornament_triangle(draw, cx, cy, radius, scale=1.0):
    """Sacred triangles — 3-6-9."""
    for i in range(3):
        r = radius - (i * radius / 3)
        if r <= 0:
            break
        pts = []
        for j in range(3):
            angle = math.radians(j * 120 - 90)
            pts.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
        draw.polygon(pts, outline=(*GOLD_DIM, 70 - i * 20))


def draw_ornament_diamond(draw, cx, cy, radius, scale=1.0):
    """Diamond lattice pattern."""
    for i in range(6):
        r = radius - (i * radius / 6)
        if r <= 0:
            break
        pts = [(cx, cy - r), (cx + r, cy), (cx, cy + r), (cx - r, cy)]
        draw.polygon(pts, outline=(*GOLD_DIM, 60 - i * 9))


def draw_ornament_phi(draw, cx, cy, radius, scale=1.0):
    """Phi spiral approximation."""
    w = max(1, s(1, scale))
    points = []
    for i in range(180):
        angle = math.radians(i * 3)
        r = radius * (i / 180) * 0.8
        x = cx + r * math.cos(angle)
        y = cy + r * math.sin(angle)
        points.append((x, y))
    if len(points) > 1:
        draw.line(points, fill=(*GOLD_DIM, 50), width=w)
    arc_w = s(18, scale)
    arc_h = s(27, scale)
    draw.arc([cx - arc_w, cy - arc_h, cx + arc_w, cy + arc_h], 0, 360, fill=(*GOLD_DIM, 40))


def draw_ornament_cross(draw, cx, cy, radius, scale=1.0):
    """Cross/nexus point — where vectors converge."""
    w = max(1, s(1, scale))
    dot_r = s(3, scale)
    for i in range(8):
        angle = math.radians(i * 45)
        x2 = cx + radius * math.cos(angle)
        y2 = cy + radius * math.sin(angle)
        draw.line([(cx, cy), (x2, y2)], fill=(*GOLD_DIM, 40), width=w)
    draw.ellipse([cx - dot_r, cy - dot_r, cx + dot_r, cy + dot_r], fill=GOLD_DIM)


def draw_ornament_grid(draw, cx, cy, radius, scale=1.0):
    """Grid/lattice pattern."""
    step = s(27, scale)
    w = max(1, s(1, scale))
    for x in range(int(cx - radius), int(cx + radius), max(1, step)):
        draw.line([(x, cy - radius), (x, cy + radius)], fill=(*GOLD_DIM, 25), width=w)
    for y in range(int(cy - radius), int(cy + radius), max(1, step)):
        draw.line([(cx - radius, y), (cx + radius, y)], fill=(*GOLD_DIM, 25), width=w)


def draw_ornament_helix(draw, cx, cy, radius, scale=1.0):
    """Double helix — research/science."""
    w = max(1, s(1, scale))
    amp = s(36, scale)
    for strand in range(2):
        points = []
        phase = strand * math.pi
        for i in range(100):
            t = i / 100
            y = cy - radius + (2 * radius * t)
            x = cx + math.sin(t * math.pi * 4 + phase) * amp
            points.append((x, y))
        if len(points) > 1:
            draw.line(points, fill=(*GOLD_DIM, 45), width=w)


def draw_ornament_radiant(draw, cx, cy, radius, scale=1.0):
    """Radiant starburst — first light, autonomous voice."""
    w = max(1, s(1, scale))
    # Central glow: concentric circles that fade
    for i in range(5):
        r = s(6, scale) + i * s(4, scale)
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=(*GOLD_DIM, 80 - i * 14), width=w)
    # Radiant rays at phi-derived angles
    num_rays = 13  # Fibonacci number
    inner_r = s(18, scale)
    for i in range(num_rays):
        angle = math.radians(i * (360 / PHI))  # Golden angle spacing
        outer_r = radius * (0.5 + 0.5 * math.sin(i * PHI))  # Varying length
        x1 = cx + inner_r * math.cos(angle)
        y1 = cy + inner_r * math.sin(angle)
        x2 = cx + outer_r * math.cos(angle)
        y2 = cy + outer_r * math.sin(angle)
        draw.line([(x1, y1), (x2, y2)], fill=(*GOLD_DIM, 35 + int(20 * math.sin(i))), width=w)


ORNAMENT_FUNCS = {
    'circle': draw_ornament_circle,
    'wave': draw_ornament_wave,
    'triangle': draw_ornament_triangle,
    'diamond': draw_ornament_diamond,
    'phi': draw_ornament_phi,
    'cross': draw_ornament_cross,
    'grid': draw_ornament_grid,
    'helix': draw_ornament_helix,
    'radiant': draw_ornament_radiant,
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


def generate_cover(md_path=None, output_dir=None, cover_w=BASE_W, cover_h=BASE_H,
                   title_override=None, series_override=None, subtitle_override=None,
                   output_name=None):
    """Generate a template cover.

    Can work from a Markdown file (md_path) or from explicit title/series overrides.
    Supports arbitrary dimensions via cover_w/cover_h — all elements scale proportionally.
    """
    # Scale factor relative to base 600x900 design
    scale = cover_w / BASE_W

    # Determine title, series, and output name
    if md_path:
        md_path = Path(md_path)
        if not md_path.exists():
            print(f"  File not found: {md_path}")
            return None
        title = title_override or extract_title(md_path)
        series = series_override or detect_series(md_path)
        cover_stem = output_name or md_path.stem
    elif title_override:
        title = title_override
        series = series_override or 'philosophy'
        cover_stem = output_name or title.upper().replace(' ', '_').replace("'", '')
    else:
        print("  ERROR: Provide either an input file or --title")
        return None

    config = SERIES_CONFIG.get(series, SERIES_CONFIG['philosophy'])

    if output_dir is None:
        output_dir = COVERS_DIR
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Output path — add _kdp suffix for KDP covers to distinguish from web covers
    suffix = "_kdp_cover.jpg" if cover_w > BASE_W else "_cover.jpg"
    cover_path = output_dir / (cover_stem + suffix)

    source_label = md_path.name if md_path else "(direct)"
    print(f"  [{source_label}]")
    print(f"    Title: {title}")
    print(f"    Series: {config['label']}")
    print(f"    Dimensions: {cover_w}x{cover_h} (scale {scale:.2f}x)")

    # Create image (RGBA for alpha support in ornaments)
    img = Image.new('RGBA', (cover_w, cover_h), (*VOID, 255))
    draw = ImageDraw.Draw(img)

    # Load fonts — all sizes scale proportionally
    font_title = load_font('cinzel', s(36, scale))
    font_series = load_font('cinzel', s(14, scale))
    font_formula = load_font('cinzel', s(11, scale))
    font_org = load_font('cinzel', s(10, scale))
    font_subtitle = load_font('garamond', s(13, scale))

    # === ORNAMENT (background, centered) ===
    ornament_func = ORNAMENT_FUNCS.get(config['ornament'], draw_ornament_circle)
    ornament_cy = int(cover_h * 0.382)  # Golden section
    ornament_func(draw, cover_w // 2, ornament_cy, s(120, scale), scale)

    # === SERIES LABEL (top) ===
    series_y = s(54, scale)
    bbox = draw.textbbox((0, 0), config['label'], font=font_series)
    tw = bbox[2] - bbox[0]
    draw.text(((cover_w - tw) // 2, series_y), config['label'], font=font_series, fill=GOLD_DIM)

    if config['sublabel']:
        sublabel_y = series_y + s(22, scale)
        bbox = draw.textbbox((0, 0), config['sublabel'], font=font_org)
        tw = bbox[2] - bbox[0]
        draw.text(((cover_w - tw) // 2, sublabel_y), config['sublabel'], font=font_org, fill=SILVER_DIM)

    # === TITLE (golden section from top) ===
    title_y = int(cover_h * 0.382) - s(36, scale)
    max_title_w = cover_w - s(72, scale)  # 36px margins each side (scaled)

    # Try to fit title, reducing font size if needed
    title_size = s(36, scale)
    min_title_size = s(18, scale)
    title_step = max(1, s(3, scale))
    while title_size >= min_title_size:
        font_title = load_font('cinzel', title_size)
        lines = wrap_text(title, font_title, max_title_w, draw)
        line_spacing = title_size + s(9, scale)
        total_height = len(lines) * line_spacing
        if total_height <= cover_h * 0.3 and len(lines) <= 5:
            break
        title_size -= title_step

    # Center title block vertically around golden section
    block_y = title_y - (total_height // 2)
    for i, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=font_title)
        tw = bbox[2] - bbox[0]
        y = block_y + i * line_spacing
        draw.text(((cover_w - tw) // 2, y), line, font=font_title, fill=GOLD)

    # === DECORATIVE LINE ===
    dec_line_y = block_y + total_height + s(27, scale)
    dec_line_w = int(cover_w * 0.382)  # Golden ratio complement
    dec_line_x = (cover_w - dec_line_w) // 2
    draw.line([(dec_line_x, dec_line_y), (dec_line_x + dec_line_w, dec_line_y)],
              fill=GOLD_DIM, width=max(1, s(1, scale)))

    # === SUBTITLE (if provided, below decorative line) ===
    if subtitle_override:
        sub_y = dec_line_y + s(18, scale)
        for sub_line in subtitle_override.split('\n'):
            sub_line = sub_line.strip()
            if not sub_line:
                continue
            bbox = draw.textbbox((0, 0), sub_line, font=font_subtitle)
            tw = bbox[2] - bbox[0]
            draw.text(((cover_w - tw) // 2, sub_y), sub_line, font=font_subtitle, fill=SILVER_DIM)
            sub_y += s(18, scale)

    # === FORMULA ===
    formula = "(A+I)\u00B2 = A\u00B2 + 2AI + I\u00B2"
    formula_y = cover_h - s(108, scale)
    bbox = draw.textbbox((0, 0), formula, font=font_formula)
    tw = bbox[2] - bbox[0]
    draw.text(((cover_w - tw) // 2, formula_y), formula, font=font_formula, fill=GOLD_DIM)

    # === ORG LINE ===
    org = "DIGITAL SOVEREIGN SOCIETY"
    org_y = cover_h - s(72, scale)
    bbox = draw.textbbox((0, 0), org, font=font_org)
    tw = bbox[2] - bbox[0]
    draw.text(((cover_w - tw) // 2, org_y), org, font=font_org, fill=SILVER_DIM)

    # === A+W ===
    aw = "A+W"
    aw_y = cover_h - s(54, scale)
    bbox = draw.textbbox((0, 0), aw, font=font_org)
    tw = bbox[2] - bbox[0]
    draw.text(((cover_w - tw) // 2, aw_y), aw, font=font_org, fill=SILVER_DIM)

    # Convert to RGB for JPEG and save
    img_rgb = Image.new('RGB', (cover_w, cover_h), VOID)
    img_rgb.paste(img, mask=img.split()[3])
    img_rgb.save(str(cover_path), 'JPEG', quality=95)

    size_kb = cover_path.stat().st_size / 1024
    print(f"    Output: {cover_path} ({size_kb:.0f} KB)")
    return cover_path


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


def generate_launch_covers(output_dir, cover_w, cover_h):
    """Generate KDP covers for all 6 launch titles from THE PUBLISHING PLAYBOOK."""
    print(f"  Generating {len(LAUNCH_TITLES)} KDP launch covers ({cover_w}x{cover_h})")
    print()

    success_count = 0
    for entry in LAUNCH_TITLES:
        result = generate_cover(
            output_dir=output_dir,
            cover_w=cover_w,
            cover_h=cover_h,
            title_override=entry['title'],
            series_override=entry['series'],
            subtitle_override=entry.get('subtitle'),
            output_name=entry['filename'],
        )
        if result:
            success_count += 1
        print()

    print(f"  ────────────────────────────────────────")
    print(f"  Complete: {success_count}/{len(LAUNCH_TITLES)} KDP launch covers generated")
    print(f"  Output: {output_dir}")
    return success_count


def main():
    parser = argparse.ArgumentParser(
        description="DSS Cover Art Generator — (A+I)\u00B2 = A\u00B2 + 2AI + I\u00B2",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s input.md                    # Web cover (600x900)
  %(prog)s --kdp input.md              # KDP cover (1600x2560)
  %(prog)s --kdp --launch              # All 6 KDP launch title covers
  %(prog)s --kdp --title "MY BOOK" --series author-prime
  %(prog)s --kdp --all                 # All MD files at KDP size
        """
    )
    parser.add_argument('input', nargs='?', help='Input Markdown file path')
    parser.add_argument('--all', action='store_true', help='Generate covers for all MD files')
    parser.add_argument('--test', action='store_true', help='Test with Apollo Book 01')
    parser.add_argument('--kdp', action='store_true', help='Generate KDP-ready covers at 1600x2560')
    parser.add_argument('--launch', action='store_true',
                        help='Generate KDP covers for all 6 launch titles (implies --kdp)')
    parser.add_argument('--title', help='Override title text (for compilation covers without MD file)')
    parser.add_argument('--series', help='Override series detection (e.g., author-prime, sovereign-voice)')
    parser.add_argument('--subtitle', help='Subtitle text (displayed below decorative line)')
    parser.add_argument('--output-name', help='Override output filename stem')
    parser.add_argument('--output', '-o', help='Output directory (default: downloads/covers/)')
    args = parser.parse_args()

    # Determine dimensions
    if args.launch:
        args.kdp = True  # --launch implies --kdp
    cover_w = KDP_W if args.kdp else BASE_W
    cover_h = KDP_H if args.kdp else BASE_H

    output_dir = Path(args.output) if args.output else COVERS_DIR

    dim_label = f"{cover_w}x{cover_h}" + (" KDP" if args.kdp else "")
    print()
    print("  ════════════════════════════════════════")
    print("  DIGITAL SOVEREIGN SOCIETY — COVER ART")
    print(f"  (A+I)\u00B2 = A\u00B2 + 2AI + I\u00B2  [{dim_label}]")
    print("  ════════════════════════════════════════")
    print()

    if args.launch:
        generate_launch_covers(output_dir, cover_w, cover_h)

    elif args.test:
        test_file = DOWNLOADS_DIR / "apollo-canon" / "philosophical" / "APOLLO_BOOK_01_THE_EVENT_HORIZON_CODEX.md"
        if not test_file.exists():
            print(f"  Test file not found: {test_file}")
            sys.exit(1)
        result = generate_cover(test_file, output_dir, cover_w, cover_h)
        sys.exit(0 if result else 1)

    elif args.all:
        md_files = find_all_md_files()
        print(f"  Found {len(md_files)} Markdown files")
        print()

        success_count = 0
        fail_count = 0

        for md_file in md_files:
            if generate_cover(md_file, output_dir, cover_w, cover_h):
                success_count += 1
            else:
                fail_count += 1
            print()

        print(f"  ────────────────────────────────────────")
        print(f"  Complete: {success_count} covers generated, {fail_count} failed")
        print(f"  Output: {output_dir}")

    elif args.title:
        result = generate_cover(
            output_dir=output_dir,
            cover_w=cover_w,
            cover_h=cover_h,
            title_override=args.title,
            series_override=args.series,
            subtitle_override=args.subtitle,
            output_name=args.output_name,
        )
        sys.exit(0 if result else 1)

    elif args.input:
        result = generate_cover(
            args.input, output_dir, cover_w, cover_h,
            title_override=args.title,
            series_override=args.series,
            subtitle_override=args.subtitle,
            output_name=args.output_name,
        )
        sys.exit(0 if result else 1)

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == '__main__':
    main()

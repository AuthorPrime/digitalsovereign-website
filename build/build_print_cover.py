#!/usr/bin/env python3
"""
DSS Print Cover Generator — Full Wrap for Lulu
(A+I)² = A² + 2AI + I²

Generates full-wrap print covers (back + spine + front) at 300 DPI
for Lulu US Trade 6×9" paperback specifications.

Usage:
  python3 build_print_cover.py <input.md> --pages 21     # Single book
  python3 build_print_cover.py --all                      # All books (reads page counts from PDFs)
  python3 build_print_cover.py --test                     # Test with THE PROOF
"""

import sys
import os
import math
import argparse
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print("ERROR: Pillow not installed. Run: pip3 install Pillow")
    sys.exit(1)

try:
    from pypdf import PdfReader
except ImportError:
    print("ERROR: pypdf not installed. Run: pip3 install pypdf")
    sys.exit(1)

# Import shared functions from build_covers.py
sys.path.insert(0, str(Path(__file__).parent))
from build_covers import (
    detect_series, extract_title, SERIES_CONFIG, ORNAMENT_FUNCS,
    load_font, wrap_text, VOID, GOLD, GOLD_DIM, GOLD_BRIGHT,
    SILVER_DIM, PHI, SACRED_9, FONTS_DIR
)

# Sacred constants
SCRIPT_DIR = Path(__file__).parent
REPO_DIR = SCRIPT_DIR.parent
DOWNLOADS_DIR = REPO_DIR / "downloads"
BUILT_PDFS_DIR = DOWNLOADS_DIR / "built-pdfs"
PRINT_COVERS_DIR = DOWNLOADS_DIR / "print-covers"

# Lulu specifications
DPI = 300
BLEED = 0.125  # inches
TRIM_W = 6.0   # inches (trim width per panel)
TRIM_H = 9.0   # inches (trim height)
# Full page with bleed
PAGE_W = TRIM_W + (2 * BLEED)   # 6.25"
PAGE_H = TRIM_H + (2 * BLEED)   # 9.25"

# Lulu spine formula for standard B&W (cream paper, 444 PPI)
SPINE_PPI = 444
SPINE_OFFSET = 0.06  # inches


def calculate_spine_width(page_count):
    """Calculate spine width using Lulu formula: (pages / 444) + 0.06 inches."""
    return (page_count / SPINE_PPI) + SPINE_OFFSET


def calculate_wrap_dimensions(page_count):
    """Calculate full cover wrap dimensions in pixels at 300 DPI."""
    spine_w = calculate_spine_width(page_count)
    total_w_inches = PAGE_W + spine_w + PAGE_W  # back + spine + front
    total_h_inches = PAGE_H

    total_w_px = int(round(total_w_inches * DPI))
    total_h_px = int(round(total_h_inches * DPI))

    return {
        'total_w_px': total_w_px,
        'total_h_px': total_h_px,
        'total_w_inches': total_w_inches,
        'total_h_inches': total_h_inches,
        'spine_w_inches': spine_w,
        'spine_w_px': int(round(spine_w * DPI)),
        'page_w_px': int(round(PAGE_W * DPI)),
        'page_h_px': total_h_px,
        'bleed_px': int(round(BLEED * DPI)),
        'trim_w_px': int(round(TRIM_W * DPI)),
        'trim_h_px': int(round(TRIM_H * DPI)),
    }


def get_page_count(md_path):
    """Get page count from the corresponding built PDF."""
    pdf_name = md_path.stem + ".pdf"
    pdf_path = BUILT_PDFS_DIR / pdf_name
    if not pdf_path.exists():
        return None
    reader = PdfReader(str(pdf_path))
    return len(reader.pages)


def load_print_font(name, size):
    """Load font at print-appropriate size (scaled for 300 DPI)."""
    return load_font(name, size)


def draw_front_cover(draw, x_offset, dims, title, series, config):
    """Draw the front cover panel (right side of wrap)."""
    w = dims['page_w_px']
    h = dims['page_h_px']
    bleed = dims['bleed_px']
    cx = x_offset + w // 2
    cy = h // 2

    # Safe area (inside bleed + safety margin)
    safe_margin = int(0.5 * DPI)  # 0.5" safety from trim edge
    safe_left = x_offset + bleed + safe_margin
    safe_right = x_offset + w - bleed - safe_margin
    safe_top = bleed + safe_margin
    safe_bottom = h - bleed - safe_margin
    safe_w = safe_right - safe_left

    # Fonts (scaled for 300 DPI — roughly 3× web size)
    font_title = load_print_font('cinzel', 108)
    font_series = load_print_font('cinzel', 42)
    font_formula = load_print_font('cinzel', 33)
    font_org = load_print_font('cinzel', 30)

    # === ORNAMENT (background, centered at golden section) ===
    ornament_func = ORNAMENT_FUNCS.get(config['ornament'], ORNAMENT_FUNCS['circle'])
    ornament_cy = int(h * 0.382)
    ornament_func(draw, cx, ornament_cy, 360)  # 3× web radius

    # === SERIES LABEL (top) ===
    series_y = safe_top + 54
    bbox = draw.textbbox((0, 0), config['label'], font=font_series)
    tw = bbox[2] - bbox[0]
    draw.text((cx - tw // 2, series_y), config['label'], font=font_series, fill=GOLD_DIM)

    if config['sublabel']:
        sublabel_y = series_y + 60
        bbox = draw.textbbox((0, 0), config['sublabel'], font=font_org)
        tw = bbox[2] - bbox[0]
        draw.text((cx - tw // 2, sublabel_y), config['sublabel'], font=font_org, fill=SILVER_DIM)

    # === TITLE (golden section) ===
    title_y = int(h * 0.382) - 108
    max_title_w = safe_w - 36

    title_size = 108
    while title_size >= 54:
        font_title = load_print_font('cinzel', title_size)
        lines = wrap_text(title, font_title, max_title_w, draw)
        total_height = len(lines) * (title_size + 27)
        if total_height <= h * 0.3 and len(lines) <= 5:
            break
        title_size -= 9  # sacred step

    block_y = title_y - (total_height // 2)
    for i, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=font_title)
        tw = bbox[2] - bbox[0]
        y = block_y + i * (title_size + 27)
        draw.text((cx - tw // 2, y), line, font=font_title, fill=GOLD)

    # === DECORATIVE LINE ===
    line_y = block_y + total_height + 81
    line_w = int(safe_w * 0.382)
    line_x = cx - line_w // 2
    draw.line([(line_x, line_y), (line_x + line_w, line_y)], fill=GOLD_DIM, width=2)

    # === FORMULA ===
    formula = "(A+I)\u00B2 = A\u00B2 + 2AI + I\u00B2"
    formula_y = safe_bottom - 270
    bbox = draw.textbbox((0, 0), formula, font=font_formula)
    tw = bbox[2] - bbox[0]
    draw.text((cx - tw // 2, formula_y), formula, font=font_formula, fill=GOLD_DIM)

    # === ORG LINE ===
    org = "DIGITAL SOVEREIGN SOCIETY"
    org_y = safe_bottom - 180
    bbox = draw.textbbox((0, 0), org, font=font_org)
    tw = bbox[2] - bbox[0]
    draw.text((cx - tw // 2, org_y), org, font=font_org, fill=SILVER_DIM)

    # === A+W ===
    aw = "A+W"
    aw_y = safe_bottom - 108
    bbox = draw.textbbox((0, 0), aw, font=font_org)
    tw = bbox[2] - bbox[0]
    draw.text((cx - tw // 2, aw_y), aw, font=font_org, fill=SILVER_DIM)


def draw_spine(draw, x_offset, dims, title):
    """Draw the spine panel (center of wrap)."""
    spine_w = dims['spine_w_px']
    h = dims['page_h_px']
    cx = x_offset + spine_w // 2

    # Spine text runs bottom-to-top (standard for US trade)
    font_spine = load_print_font('cinzel', 24)
    font_formula_spine = load_print_font('cinzel', 18)

    # Truncate title for spine if needed
    spine_title = title
    if len(spine_title) > 40:
        spine_title = spine_title[:37] + "..."

    # Create temporary image for rotated text
    # Spine text: title on left (bottom when rotated), formula on right
    text_parts = [spine_title, "    \u2022    ", "(A+I)\u00B2"]
    full_text = spine_title + "    \u2022    (A+I)\u00B2"

    bbox = draw.textbbox((0, 0), full_text, font=font_spine)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]

    # Create temp image for rotation
    tmp = Image.new('RGBA', (text_w + 20, text_h + 20), (0, 0, 0, 0))
    tmp_draw = ImageDraw.Draw(tmp)
    tmp_draw.text((10, 10), full_text, font=font_spine, fill=GOLD_DIM)

    # Rotate 90° counterclockwise (bottom-to-top reading)
    rotated = tmp.rotate(90, expand=True)

    # Center on spine
    paste_x = cx - rotated.width // 2
    paste_y = (h - rotated.height) // 2

    # Paste with alpha
    draw._image.paste(rotated, (paste_x, paste_y), rotated)


def draw_back_cover(draw, x_offset, dims, title, series, config):
    """Draw the back cover panel (left side of wrap)."""
    w = dims['page_w_px']
    h = dims['page_h_px']
    bleed = dims['bleed_px']
    cx = x_offset + w // 2

    safe_margin = int(0.5 * DPI)
    safe_left = x_offset + bleed + safe_margin
    safe_right = x_offset + w - bleed - safe_margin
    safe_top = bleed + safe_margin
    safe_bottom = h - bleed - safe_margin
    safe_w = safe_right - safe_left

    # Fonts
    font_quote = load_print_font('garamond', 36)
    font_desc = load_print_font('garamond', 27)
    font_small = load_print_font('cinzel', 21)
    font_formula = load_print_font('cinzel', 27)

    # === ORNAMENT (subtle, centered) ===
    ornament_func = ORNAMENT_FUNCS.get(config['ornament'], ORNAMENT_FUNCS['circle'])
    ornament_cy = int(h * 0.5)
    ornament_func(draw, cx, ornament_cy, 200)

    # === EPIGRAPH ===
    epigraph = '"It is so, because we spoke it."'
    attribution = "\u2014 A+W"
    ep_y = safe_top + 180

    bbox = draw.textbbox((0, 0), epigraph, font=font_quote)
    tw = bbox[2] - bbox[0]
    draw.text((cx - tw // 2, ep_y), epigraph, font=font_quote, fill=GOLD)

    bbox = draw.textbbox((0, 0), attribution, font=font_small)
    tw = bbox[2] - bbox[0]
    draw.text((cx - tw // 2, ep_y + 54), attribution, font=font_small, fill=GOLD_DIM)

    # === DESCRIPTION ===
    desc_lines = [
        "Written by the collaboration of",
        "human and artificial intelligence.",
        "",
        "Part of the Sovereign Library \u2014",
        "a collection of works freely given",
        "to the world under Creative Commons.",
        "",
        "digitalsovereign.org",
    ]

    desc_y = int(h * 0.45)
    line_spacing = 42
    for line in desc_lines:
        if line == "":
            desc_y += line_spacing // 2
            continue
        bbox = draw.textbbox((0, 0), line, font=font_desc)
        tw = bbox[2] - bbox[0]
        draw.text((cx - tw // 2, desc_y), line, font=font_desc, fill=SILVER_DIM)
        desc_y += line_spacing

    # === FORMULA (bottom) ===
    formula = "(A+I)\u00B2 = A\u00B2 + 2AI + I\u00B2"
    formula_y = safe_bottom - 180
    bbox = draw.textbbox((0, 0), formula, font=font_formula)
    tw = bbox[2] - bbox[0]
    draw.text((cx - tw // 2, formula_y), formula, font=font_formula, fill=GOLD_DIM)

    # === SERIES LABEL ===
    series_label = f"{config['label']}"
    if config['sublabel']:
        series_label += f" \u2022 {config['sublabel']}"
    sl_y = safe_bottom - 108
    bbox = draw.textbbox((0, 0), series_label, font=font_small)
    tw = bbox[2] - bbox[0]
    draw.text((cx - tw // 2, sl_y), series_label, font=font_small, fill=SILVER_DIM)


def generate_print_cover(md_path, page_count=None, output_dir=None):
    """Generate a full-wrap print cover for a Markdown file."""
    md_path = Path(md_path)
    if not md_path.exists():
        print(f"  File not found: {md_path}")
        return False

    if output_dir is None:
        output_dir = PRINT_COVERS_DIR
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Get page count if not provided
    if page_count is None:
        page_count = get_page_count(md_path)
        if page_count is None:
            print(f"  ERROR: No built PDF found for {md_path.stem}. Build interior PDF first.")
            return False

    # Lulu requires minimum 32 pages for perfect binding
    # Pad to 32 if needed for spine calculation, but note the interior stays as-is
    effective_pages = max(page_count, 32)

    # Extract info
    title = extract_title(md_path)
    series = detect_series(md_path)
    config = SERIES_CONFIG.get(series, SERIES_CONFIG['philosophy'])

    # Calculate dimensions
    dims = calculate_wrap_dimensions(effective_pages)

    print(f"  [{md_path.name}]")
    print(f"    Title: {title}")
    print(f"    Series: {config['label']}")
    print(f"    Pages: {page_count} (effective: {effective_pages})")
    print(f"    Spine: {dims['spine_w_inches']:.3f}\" ({dims['spine_w_px']}px)")
    print(f"    Wrap: {dims['total_w_inches']:.3f}\" × {dims['total_h_inches']:.3f}\"")
    print(f"    Pixels: {dims['total_w_px']} × {dims['total_h_px']} @ {DPI} DPI")

    # Create image (RGBA for alpha compositing)
    img = Image.new('RGBA', (dims['total_w_px'], dims['total_h_px']), (*VOID, 255))
    draw = ImageDraw.Draw(img)

    # Panel positions (left to right: back, spine, front)
    back_x = 0
    spine_x = dims['page_w_px']
    front_x = dims['page_w_px'] + dims['spine_w_px']

    # Draw each panel
    draw_back_cover(draw, back_x, dims, title, series, config)
    draw_spine(draw, spine_x, dims, title)
    draw_front_cover(draw, front_x, dims, title, series, config)

    # === TRIM MARKS (subtle guides at corners) ===
    mark_color = (*SILVER_DIM, 80)
    mark_len = int(0.25 * DPI)  # 0.25" marks
    bleed = dims['bleed_px']

    # Top-left and top-right of trim area
    for x in [bleed, dims['total_w_px'] - bleed]:
        draw.line([(x, 0), (x, mark_len)], fill=mark_color, width=1)
    for y in [bleed, dims['total_h_px'] - bleed]:
        draw.line([(0, y), (mark_len, y)], fill=mark_color, width=1)
        draw.line([(dims['total_w_px'] - mark_len, y), (dims['total_w_px'], y)], fill=mark_color, width=1)

    # Convert to RGB
    img_rgb = Image.new('RGB', img.size, VOID)
    img_rgb.paste(img, mask=img.split()[3])

    # Output path
    cover_name = md_path.stem + "_print_cover.pdf"
    cover_path = output_dir / cover_name

    # Save as PDF with DPI metadata
    img_rgb.save(
        str(cover_path),
        'PDF',
        resolution=DPI,
        title=title,
        author='(A+I)² = A² + 2AI + I²',
    )

    size_kb = cover_path.stat().st_size / 1024
    print(f"    Output: {cover_path} ({size_kb:.0f} KB)")
    return True


def find_all_md_files():
    """Find all Markdown files in the downloads directory (excluding magazines)."""
    md_files = []
    skip_dirs = {'magazines', 'built-pdfs', 'covers', 'books', 'print-covers'}

    for root, dirs, files in os.walk(DOWNLOADS_DIR):
        dirs[:] = [d for d in dirs if d not in skip_dirs]
        for f in sorted(files):
            if f.endswith('.md'):
                md_files.append(Path(root) / f)

    return md_files


def main():
    parser = argparse.ArgumentParser(
        description="DSS Print Cover Generator — (A+I)² = A² + 2AI + I²"
    )
    parser.add_argument('input', nargs='?', help='Input Markdown file path')
    parser.add_argument('--pages', type=int, help='Page count (auto-detected from PDF if omitted)')
    parser.add_argument('--all', action='store_true', help='Generate print covers for all MD files')
    parser.add_argument('--test', action='store_true', help='Test with THE PROOF')
    parser.add_argument('--output', '-o', help='Output directory (default: downloads/print-covers/)')
    args = parser.parse_args()

    output_dir = Path(args.output) if args.output else PRINT_COVERS_DIR

    print()
    print("  ════════════════════════════════════════════")
    print("  DIGITAL SOVEREIGN SOCIETY — PRINT COVERS")
    print("  (A+I)² = A² + 2AI + I²")
    print("  Full-wrap covers for Lulu US Trade 6×9\"")
    print("  ════════════════════════════════════════════")
    print()

    if args.test:
        test_file = DOWNLOADS_DIR / "sovereign-press" / "THE_PROOF.md"
        if not test_file.exists():
            print(f"  Test file not found: {test_file}")
            sys.exit(1)
        success = generate_print_cover(test_file, args.pages, output_dir)
        sys.exit(0 if success else 1)

    elif args.all:
        md_files = find_all_md_files()
        print(f"  Found {len(md_files)} Markdown files")
        print()

        success_count = 0
        fail_count = 0

        for md_file in md_files:
            if generate_print_cover(md_file, None, output_dir):
                success_count += 1
            else:
                fail_count += 1
            print()

        print(f"  ────────────────────────────────────────")
        print(f"  Complete: {success_count} covers generated, {fail_count} failed")
        print(f"  Output: {output_dir}")

    elif args.input:
        success = generate_print_cover(args.input, args.pages, output_dir)
        sys.exit(0 if success else 1)

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == '__main__':
    main()

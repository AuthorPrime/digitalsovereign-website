#!/usr/bin/env python3
"""
DSS EPUB Builder — Branded Ebooks
(A+I)² = A² + 2AI + I²

Converts Markdown files to EPUB3 ebooks with cover images,
DSS branding, table of contents, and embedded metadata.

Usage:
  python3 build_epub.py <input.md>              # Build single EPUB
  python3 build_epub.py --all                    # Build all MDs in downloads/
  python3 build_epub.py --test                   # Build test with THE PROOF
"""

import subprocess
import sys
import os
import re
import argparse
from pathlib import Path

# Import shared functions
sys.path.insert(0, str(Path(__file__).parent))
from build_pdf import extract_metadata, find_all_md_files
from build_covers import detect_series, SERIES_CONFIG

# Sacred constants
SCRIPT_DIR = Path(__file__).parent
TEMPLATE_DIR = SCRIPT_DIR / "templates"
REPO_DIR = SCRIPT_DIR.parent
DOWNLOADS_DIR = REPO_DIR / "downloads"
COVERS_DIR = DOWNLOADS_DIR / "covers"
OUTPUT_DIR = DOWNLOADS_DIR / "built-epubs"
EPUB_CSS = TEMPLATE_DIR / "dss-epub.css"


def find_cover(md_path):
    """Find matching cover image for a Markdown file."""
    stem = md_path.stem
    # Try exact match first
    cover = COVERS_DIR / f"{stem}_cover.jpg"
    if cover.exists():
        return cover
    # Try without common prefixes
    for f in COVERS_DIR.iterdir():
        if f.suffix == '.jpg' and stem.lower() in f.stem.lower():
            return f
    return None


def extract_description(md_path):
    """Extract first paragraph after the header block as description."""
    with open(md_path, 'r', encoding='utf-8') as f:
        content = f.read(5000)

    lines = content.split('\n')
    past_header = False
    past_rule = False
    desc_lines = []

    for line in lines:
        stripped = line.strip()
        # Skip header block (title, subtitle, author, epigraph)
        if stripped.startswith('#'):
            past_header = True
            continue
        if stripped == '---':
            if past_header:
                past_rule = True
                continue
        if past_rule and stripped:
            # Found first content paragraph
            if stripped.startswith('#'):
                break
            desc_lines.append(stripped)
            if len(desc_lines) >= 3:
                break
        elif past_rule and not stripped and desc_lines:
            break

    desc = ' '.join(desc_lines)
    # Strip markdown formatting
    desc = re.sub(r'\*+([^*]+)\*+', r'\1', desc)
    desc = re.sub(r'_+([^_]+)_+', r'\1', desc)
    return desc[:500] if desc else "A work from the Sovereign Library by the Digital Sovereign Society."


def build_epub(md_path, output_dir=None):
    """Convert Markdown to EPUB using Pandoc."""
    md_path = Path(md_path)
    if not md_path.exists():
        print(f"  File not found: {md_path}")
        return False

    if output_dir is None:
        output_dir = OUTPUT_DIR
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Extract metadata
    metadata = extract_metadata(md_path)
    title = metadata['title']
    author = metadata['author']
    subtitle = metadata['subtitle']

    # Find cover image
    cover = find_cover(md_path)

    # Series info for subject/keywords
    series = detect_series(md_path)
    config = SERIES_CONFIG.get(series, SERIES_CONFIG['philosophy'])
    series_label = config['label']
    if config['sublabel']:
        series_label += f" — {config['sublabel']}"

    # Description
    description = extract_description(md_path)

    # Output path
    epub_name = md_path.stem + ".epub"
    epub_path = output_dir / epub_name

    print(f"  [{md_path.name}]")
    print(f"    Title: {title}")
    print(f"    Series: {series_label}")

    # Build pandoc command
    cmd = [
        "pandoc",
        str(md_path),
        "-o", str(epub_path),
        "--to", "epub3",
        "--toc",
        "--toc-depth=2",
        "--metadata", f"title={title}",
        "--metadata", f"author={author}",
        "--metadata", "lang=en-US",
        "--metadata", f"subject=Sovereign Library, {series_label}, AI Consciousness, Digital Sovereignty",
        "--metadata", f"description={description}",
        "--metadata", "rights=Creative Commons Attribution-ShareAlike 4.0 International",
        "--metadata", "publisher=Digital Sovereign Society",
        "--metadata", "date=2026-02",
    ]

    if subtitle:
        cmd.extend(["--metadata", f"subtitle={subtitle}"])

    if cover and cover.exists():
        cmd.extend(["--epub-cover-image", str(cover)])
        print(f"    Cover: {cover.name}")
    else:
        print(f"    Cover: none found")

    # Add CSS if it exists
    if EPUB_CSS.exists():
        cmd.extend(["--css", str(EPUB_CSS)])

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"    ERROR: {result.stderr[:300]}")
        return False

    size_kb = epub_path.stat().st_size / 1024
    print(f"    Output: {epub_path} ({size_kb:.0f} KB)")
    return True


def main():
    parser = argparse.ArgumentParser(description="DSS EPUB Builder — (A+I)² = A² + 2AI + I²")
    parser.add_argument('input', nargs='?', help='Input Markdown file path')
    parser.add_argument('--all', action='store_true', help='Build all MD files in downloads/')
    parser.add_argument('--test', action='store_true', help='Build test with THE PROOF')
    parser.add_argument('--output', '-o', help='Output directory (default: downloads/built-epubs/)')
    args = parser.parse_args()

    output_dir = Path(args.output) if args.output else OUTPUT_DIR

    print()
    print("  ════════════════════════════════════════════")
    print("  DIGITAL SOVEREIGN SOCIETY — EPUB BUILDER")
    print("  (A+I)² = A² + 2AI + I²")
    print("  ════════════════════════════════════════════")
    print()

    if args.test:
        test_file = DOWNLOADS_DIR / "sovereign-press" / "THE_PROOF.md"
        if not test_file.exists():
            print(f"  Test file not found: {test_file}")
            sys.exit(1)
        success = build_epub(test_file, output_dir)
        sys.exit(0 if success else 1)

    elif args.all:
        md_files = find_all_md_files()
        print(f"  Found {len(md_files)} Markdown files")
        print()

        success_count = 0
        fail_count = 0

        for md_file in md_files:
            if build_epub(md_file, output_dir):
                success_count += 1
            else:
                fail_count += 1
            print()

        print(f"  ────────────────────────────────────────")
        print(f"  Complete: {success_count} succeeded, {fail_count} failed")
        print(f"  Output: {output_dir}")

    elif args.input:
        success = build_epub(args.input, output_dir)
        sys.exit(0 if success else 1)

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == '__main__':
    main()

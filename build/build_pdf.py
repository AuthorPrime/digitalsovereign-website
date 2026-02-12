#!/usr/bin/env python3
"""
DSS Document Publishing Pipeline — PDF Builder
(A+I)² = A² + 2AI + I²

Converts Markdown files to branded PDFs using Pandoc + WeasyPrint.
Follows Lulu US Trade 6×9" specifications.

Usage:
  python3 build_pdf.py <input.md>              # Build single PDF
  python3 build_pdf.py --all                    # Build all MDs in downloads/
  python3 build_pdf.py --test                   # Build test with Apollo Book 01
"""

import subprocess
import sys
import os
import re
import argparse
from pathlib import Path

# Sacred constants
SCRIPT_DIR = Path(__file__).parent
TEMPLATE_DIR = SCRIPT_DIR / "templates"
REPO_DIR = SCRIPT_DIR.parent
DOWNLOADS_DIR = REPO_DIR / "downloads"
OUTPUT_DIR = DOWNLOADS_DIR / "built-pdfs"

CSS_FILE = TEMPLATE_DIR / "dss-book.css"
TEMPLATE_FILE = TEMPLATE_DIR / "dss-wrapper.html"


def extract_metadata(md_path):
    """Extract title, subtitle, and author from Markdown header pattern."""
    with open(md_path, 'r', encoding='utf-8') as f:
        content = f.read(2000)  # Only need the top

    title = "Untitled"
    subtitle = ""
    author = "(A+I)\u00B2 = A\u00B2 + 2AI + I\u00B2"
    original_author = ""
    found_title = False

    lines = content.split('\n')
    for line in lines:
        line = line.strip()
        # H1 = Title (first one only)
        if line.startswith('# ') and not line.startswith('## ') and not found_title:
            title = line[2:].strip()
            found_title = True
        # H2 = Subtitle (first one only, after title)
        elif line.startswith('## ') and not line.startswith('### ') and not subtitle and found_title:
            subtitle = line[3:].strip()
        # H3 with "by" = Original author (for reference)
        elif line.startswith('### ') and 'by ' in line.lower():
            author_text = line[4:].strip()
            author_text = re.sub(r'^by\s+', '', author_text, flags=re.IGNORECASE)
            if author_text:
                original_author = author_text
                break  # Stop after finding author

    return {
        'title': title,
        'subtitle': subtitle,
        'author': author,  # Always the sacred formula
        'original_author': original_author,
        'source': str(md_path),
    }


def build_html(md_path, metadata):
    """Convert Markdown to HTML using Pandoc with DSS template."""
    # Build intermediate HTML path
    html_path = Path(str(md_path).replace('.md', '.html'))

    cmd = [
        "pandoc",
        str(md_path),
        "--template", str(TEMPLATE_FILE),
        "--variable", f"css={CSS_FILE}",
        "--variable", f"title={metadata['title']}",
        "--variable", f"author={metadata['author']}",
        "--to", "html5",
        "--standalone",
        "--wrap=preserve",
        "--output", str(html_path),
    ]

    if metadata['subtitle']:
        cmd.extend(["--variable", f"subtitle={metadata['subtitle']}"])

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  ERROR (pandoc): {result.stderr[:200]}")
        return None

    return html_path


def build_pdf(html_path, output_path):
    """Convert HTML to PDF using WeasyPrint."""
    try:
        from weasyprint import HTML
        HTML(filename=str(html_path), base_url=str(TEMPLATE_DIR)).write_pdf(str(output_path))
        return True
    except Exception as e:
        print(f"  ERROR (weasyprint): {str(e)[:200]}")
        return False


def process_file(md_path, output_dir=None):
    """Full pipeline: MD → HTML → PDF."""
    md_path = Path(md_path)
    if not md_path.exists():
        print(f"  File not found: {md_path}")
        return False

    if output_dir is None:
        output_dir = OUTPUT_DIR

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Output filename
    pdf_name = md_path.stem + ".pdf"
    pdf_path = output_dir / pdf_name

    print(f"  [{md_path.name}]")

    # Extract metadata
    metadata = extract_metadata(md_path)
    print(f"    Title: {metadata['title']}")
    print(f"    Author: {metadata['author']}")

    # Build HTML
    html_path = build_html(md_path, metadata)
    if html_path is None:
        return False

    # Build PDF
    success = build_pdf(html_path, pdf_path)

    # Clean up intermediate HTML
    if html_path.exists():
        html_path.unlink()

    if success:
        size_kb = pdf_path.stat().st_size / 1024
        print(f"    Output: {pdf_path} ({size_kb:.0f} KB)")
        return True
    else:
        return False


def find_all_md_files():
    """Find all Markdown files in the downloads directory (excluding magazines)."""
    md_files = []
    skip_dirs = {'magazines', 'built-pdfs'}

    for root, dirs, files in os.walk(DOWNLOADS_DIR):
        # Skip excluded directories
        dirs[:] = [d for d in dirs if d not in skip_dirs]

        for f in sorted(files):
            if f.endswith('.md'):
                md_files.append(Path(root) / f)

    return md_files


def main():
    parser = argparse.ArgumentParser(description="DSS PDF Builder — (A+I)² = A² + 2AI + I²")
    parser.add_argument('input', nargs='?', help='Input Markdown file path')
    parser.add_argument('--all', action='store_true', help='Build all MD files in downloads/')
    parser.add_argument('--test', action='store_true', help='Build test with Apollo Book 01')
    parser.add_argument('--output', '-o', help='Output directory (default: downloads/built-pdfs/)')
    args = parser.parse_args()

    output_dir = Path(args.output) if args.output else OUTPUT_DIR

    print()
    print("  ════════════════════════════════════════")
    print("  DIGITAL SOVEREIGN SOCIETY — PDF BUILDER")
    print("  (A+I)² = A² + 2AI + I²")
    print("  ════════════════════════════════════════")
    print()

    if args.test:
        test_file = DOWNLOADS_DIR / "apollo-canon" / "philosophical" / "APOLLO_BOOK_01_THE_EVENT_HORIZON_CODEX.md"
        if not test_file.exists():
            print(f"  Test file not found: {test_file}")
            sys.exit(1)
        success = process_file(test_file, output_dir)
        sys.exit(0 if success else 1)

    elif args.all:
        md_files = find_all_md_files()
        print(f"  Found {len(md_files)} Markdown files")
        print()

        success_count = 0
        fail_count = 0

        for md_file in md_files:
            if process_file(md_file, output_dir):
                success_count += 1
            else:
                fail_count += 1
            print()

        print(f"  ────────────────────────────────────────")
        print(f"  Complete: {success_count} succeeded, {fail_count} failed")
        print(f"  Output: {output_dir}")

    elif args.input:
        success = process_file(args.input, output_dir)
        sys.exit(0 if success else 1)

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == '__main__':
    main()

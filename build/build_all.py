#!/usr/bin/env python3
"""
DSS Build All — Single-File Publishing Pipeline
(A+I)² = A² + 2AI + I²

Runs the full build pipeline for a Markdown file:
  1. Cover art (so EPUB can embed it)
  2. PDF (branded, Lulu 6×9")
  3. EPUB (with cover embedded)

Usage:
  python3 build_all.py <input.md>         # Build all formats for one file
  python3 build_all.py --all              # Build all formats for all files
"""

import sys
import argparse
from pathlib import Path

# Import the individual builders
sys.path.insert(0, str(Path(__file__).parent))
from build_covers import generate_cover, find_all_md_files as find_all_cover_files, COVERS_DIR
from build_pdf import process_file as build_pdf, OUTPUT_DIR as PDF_DIR
from build_epub import build_epub, OUTPUT_DIR as EPUB_DIR


def build_all_formats(md_path):
    """Run full pipeline: cover → PDF → EPUB."""
    md_path = Path(md_path)
    if not md_path.exists():
        print(f"  File not found: {md_path}")
        return False

    results = {}

    # 1. Cover art first (EPUB needs it)
    print(f"  ── Cover ──")
    results['cover'] = generate_cover(md_path)
    print()

    # 2. PDF
    print(f"  ── PDF ──")
    results['pdf'] = build_pdf(md_path)
    print()

    # 3. EPUB (cover should now exist)
    print(f"  ── EPUB ──")
    results['epub'] = build_epub(md_path)
    print()

    succeeded = sum(1 for v in results.values() if v)
    failed = sum(1 for v in results.values() if not v)
    print(f"  Result: {succeeded}/3 formats built ({failed} failed)")

    return all(results.values())


def main():
    parser = argparse.ArgumentParser(description="DSS Build All — (A+I)² = A² + 2AI + I²")
    parser.add_argument('input', nargs='?', help='Input Markdown file path')
    parser.add_argument('--all', action='store_true', help='Build all formats for all MD files')
    args = parser.parse_args()

    print()
    print("  ════════════════════════════════════════════")
    print("  DIGITAL SOVEREIGN SOCIETY — FULL PIPELINE")
    print("  Cover → PDF → EPUB")
    print("  (A+I)² = A² + 2AI + I²")
    print("  ════════════════════════════════════════════")
    print()

    if args.all:
        from build_pdf import find_all_md_files
        md_files = find_all_md_files()
        print(f"  Found {len(md_files)} Markdown files")
        print()

        success_count = 0
        fail_count = 0

        for md_file in md_files:
            print(f"  ╔══ {md_file.name} ══╗")
            if build_all_formats(md_file):
                success_count += 1
            else:
                fail_count += 1
            print()

        print(f"  ════════════════════════════════════════════")
        print(f"  Complete: {success_count} fully built, {fail_count} with errors")

    elif args.input:
        success = build_all_formats(args.input)
        sys.exit(0 if success else 1)

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == '__main__':
    main()

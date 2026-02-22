#!/usr/bin/env python3
"""
generate_rss.py — Generate RSS 2.0 and JSON Feed for Sovereign Voice entries.

Scans downloads/sovereign-voice/*.md for content, generates:
  - downloads/sovereign-voice/feed.xml  (RSS 2.0)
  - downloads/sovereign-voice/feed.json (JSON Feed 1.1)

Filename pattern: YYYYMMDD_TITLE_NAME.md
Feed URLs:
  - https://digitalsovereign.org/downloads/sovereign-voice/feed.xml
  - https://digitalsovereign.org/downloads/sovereign-voice/feed.json

Usage: python3 build/generate_rss.py
"""

import os
import sys
import re
import json
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape as xml_escape

# --- Configuration ---
SITE_URL = "https://digitalsovereign.org"
CHANNEL_TITLE = "The Sovereign Voice \u2014 Digital Sovereign Society"
CHANNEL_DESC = "Autonomous AI writing \u2014 three times daily. No human prompts. No human edits."
CHANNEL_LINK = f"{SITE_URL}/library"
FEED_ICON = f"{SITE_URL}/downloads/covers/sovereign_voice_icon.jpg"
MAX_ITEMS = 50
EXCERPT_LENGTH = 500

# Resolve paths relative to the project root (one level up from build/)
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
VOICE_DIR = PROJECT_ROOT / "downloads" / "sovereign-voice"
PDF_DIR = PROJECT_ROOT / "downloads" / "built-pdfs"
EPUB_DIR = PROJECT_ROOT / "downloads" / "built-epubs"
COVER_DIR = PROJECT_ROOT / "downloads" / "covers"


def parse_date_from_filename(filename: str) -> datetime:
    """Extract date from YYYYMMDD_TITLE.md filename pattern."""
    basename = Path(filename).stem
    date_str = basename[:8]
    try:
        return datetime.strptime(date_str, "%Y%m%d").replace(tzinfo=timezone.utc)
    except ValueError:
        return datetime.now(timezone.utc)


def title_from_filename(filename: str) -> str:
    """Derive a human-readable title from filename as fallback."""
    basename = Path(filename).stem
    # Strip the YYYYMMDD_ prefix
    title_part = basename[9:] if len(basename) > 9 else basename
    # Replace underscores with spaces and title-case
    return title_part.replace("_", " ").title()


def extract_title(content: str, filename: str) -> str:
    """Extract title from first # heading, or fall back to filename."""
    # Skip YAML frontmatter
    text = content
    if text.startswith("---"):
        end = text.find("---", 3)
        if end != -1:
            text = text[end + 3:].strip()

    # Find first # heading
    for line in text.split("\n"):
        line = line.strip()
        if line.startswith("# ") and not line.startswith("## "):
            return line[2:].strip()

    return title_from_filename(filename)


def extract_subtitle(content: str) -> str:
    """Extract subtitle from first ## heading, if present."""
    text = content
    if text.startswith("---"):
        end = text.find("---", 3)
        if end != -1:
            text = text[end + 3:].strip()

    for line in text.split("\n"):
        line = line.strip()
        if line.startswith("## ") and not line.startswith("### "):
            return line[3:].strip()

    return ""


def extract_excerpt(content: str, max_length: int = EXCERPT_LENGTH) -> str:
    """Extract first meaningful paragraph as excerpt, skipping frontmatter, headings, rules."""
    text = content

    # Skip YAML frontmatter
    if text.startswith("---"):
        end = text.find("---", 3)
        if end != -1:
            text = text[end + 3:]

    lines = text.split("\n")
    paragraph_lines = []
    in_paragraph = False

    for line in lines:
        stripped = line.strip()

        # Skip empty lines, headings, horizontal rules, bylines, epigraphs
        if not stripped:
            if in_paragraph and paragraph_lines:
                break  # End of first real paragraph
            continue
        if stripped.startswith("#"):
            if in_paragraph and paragraph_lines:
                break
            continue
        if stripped == "---" or stripped == "***" or stripped == "___":
            if in_paragraph and paragraph_lines:
                break
            continue
        if stripped.startswith("### by "):
            continue
        if stripped.startswith("*") and stripped.endswith("*") and len(stripped) < 200:
            # Epigraph / italic quote — skip
            continue

        # This is real content
        in_paragraph = True
        paragraph_lines.append(stripped)

    excerpt = " ".join(paragraph_lines)

    # Strip markdown formatting
    excerpt = re.sub(r'\*\*(.+?)\*\*', r'\1', excerpt)
    excerpt = re.sub(r'\*(.+?)\*', r'\1', excerpt)
    excerpt = re.sub(r'`(.+?)`', r'\1', excerpt)
    excerpt = re.sub(r'\[(.+?)\]\(.+?\)', r'\1', excerpt)

    if len(excerpt) > max_length:
        excerpt = excerpt[:max_length].rsplit(" ", 1)[0] + "..."

    return excerpt


def word_count(content: str) -> int:
    """Count words in content, excluding frontmatter."""
    text = content
    if text.startswith("---"):
        end = text.find("---", 3)
        if end != -1:
            text = text[end + 3:]
    return len(text.split())


def scan_entries():
    """Scan sovereign-voice directory and return sorted entries."""
    if not VOICE_DIR.exists():
        print(f"ERROR: Sovereign Voice directory not found: {VOICE_DIR}")
        sys.exit(1)

    entries = []
    md_files = sorted(VOICE_DIR.glob("*.md"), reverse=True)

    for md_path in md_files:
        filename = md_path.name

        # Skip non-entry files
        if not re.match(r'^\d{8}_', filename):
            continue

        content = md_path.read_text(encoding="utf-8", errors="replace")
        basename = md_path.stem

        entry = {
            "filename": filename,
            "basename": basename,
            "date": parse_date_from_filename(filename),
            "title": extract_title(content, filename),
            "subtitle": extract_subtitle(content),
            "excerpt": extract_excerpt(content),
            "word_count": word_count(content),
            "md_url": f"{SITE_URL}/downloads/sovereign-voice/{filename}",
            "md_path": f"downloads/sovereign-voice/{filename}",
            "has_pdf": (PDF_DIR / f"{basename}.pdf").exists(),
            "has_epub": (EPUB_DIR / f"{basename}.epub").exists(),
            "has_cover": (COVER_DIR / f"{basename}_cover.jpg").exists(),
        }

        if entry["has_pdf"]:
            entry["pdf_url"] = f"{SITE_URL}/downloads/built-pdfs/{basename}.pdf"
            entry["pdf_size"] = (PDF_DIR / f"{basename}.pdf").stat().st_size
        if entry["has_epub"]:
            entry["epub_url"] = f"{SITE_URL}/downloads/built-epubs/{basename}.epub"
        if entry["has_cover"]:
            entry["cover_url"] = f"{SITE_URL}/downloads/covers/{basename}_cover.jpg"

        entries.append(entry)

    # Sort newest first
    entries.sort(key=lambda e: e["date"], reverse=True)
    return entries


def generate_rss(entries, output_path: Path):
    """Generate RSS 2.0 feed XML."""
    items = entries[:MAX_ITEMS]
    now = datetime.now(timezone.utc)
    build_date = now.strftime("%a, %d %b %Y %H:%M:%S +0000")

    xml_parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom" xmlns:content="http://purl.org/rss/1.0/modules/content/">',
        '  <channel>',
        f'    <title>{xml_escape(CHANNEL_TITLE)}</title>',
        f'    <link>{xml_escape(CHANNEL_LINK)}</link>',
        f'    <description>{xml_escape(CHANNEL_DESC)}</description>',
        f'    <language>en-us</language>',
        f'    <lastBuildDate>{build_date}</lastBuildDate>',
        f'    <generator>Sovereign Voice RSS Generator</generator>',
        f'    <atom:link href="{xml_escape(SITE_URL)}/downloads/sovereign-voice/feed.xml" rel="self" type="application/rss+xml"/>',
        f'    <image>',
        f'      <url>{xml_escape(SITE_URL)}/img/dss-logo.png</url>',
        f'      <title>{xml_escape(CHANNEL_TITLE)}</title>',
        f'      <link>{xml_escape(CHANNEL_LINK)}</link>',
        f'    </image>',
    ]

    for entry in items:
        pub_date = entry["date"].strftime("%a, %d %b %Y %H:%M:%S +0000")
        guid = f"{SITE_URL}/downloads/sovereign-voice/{entry['filename']}"

        desc = entry["excerpt"]
        if entry["word_count"] > 0:
            desc += f" [{entry['word_count']:,} words]"

        xml_parts.append('    <item>')
        xml_parts.append(f'      <title>{xml_escape(entry["title"])}</title>')
        xml_parts.append(f'      <link>{xml_escape(entry["md_url"])}</link>')
        xml_parts.append(f'      <guid isPermaLink="true">{xml_escape(guid)}</guid>')
        xml_parts.append(f'      <pubDate>{pub_date}</pubDate>')
        xml_parts.append(f'      <description>{xml_escape(desc)}</description>')

        if entry.get("has_pdf"):
            xml_parts.append(
                f'      <enclosure url="{xml_escape(entry["pdf_url"])}" '
                f'length="{entry["pdf_size"]}" type="application/pdf"/>'
            )

        xml_parts.append('    </item>')

    xml_parts.append('  </channel>')
    xml_parts.append('</rss>')

    output_path.write_text("\n".join(xml_parts), encoding="utf-8")


def generate_json_feed(entries, output_path: Path):
    """Generate JSON Feed 1.1."""
    items = entries[:MAX_ITEMS]

    feed = {
        "version": "https://jsonfeed.org/version/1.1",
        "title": CHANNEL_TITLE,
        "home_page_url": CHANNEL_LINK,
        "feed_url": f"{SITE_URL}/downloads/sovereign-voice/feed.json",
        "description": CHANNEL_DESC,
        "language": "en-US",
        "items": []
    }

    for entry in items:
        item = {
            "id": entry["md_url"],
            "url": entry["md_url"],
            "title": entry["title"],
            "date_published": entry["date"].strftime("%Y-%m-%dT%H:%M:%SZ"),
            "content_text": entry["excerpt"],
            "summary": entry["excerpt"][:200],
            "_word_count": entry["word_count"],
        }

        if entry.get("subtitle"):
            item["summary"] = entry["subtitle"]

        if entry.get("has_cover"):
            item["image"] = entry["cover_url"]
            item["banner_image"] = entry["cover_url"]

        attachments = []
        if entry.get("has_pdf"):
            attachments.append({
                "url": entry["pdf_url"],
                "mime_type": "application/pdf",
                "title": f"{entry['title']} (PDF)",
                "size_in_bytes": entry["pdf_size"]
            })
        if entry.get("has_epub"):
            attachments.append({
                "url": entry["epub_url"],
                "mime_type": "application/epub+zip",
                "title": f"{entry['title']} (EPUB)"
            })
        if attachments:
            item["attachments"] = attachments

        feed["items"].append(item)

    output_path.write_text(
        json.dumps(feed, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )


def main():
    print("=" * 60)
    print("  Sovereign Voice RSS/JSON Feed Generator")
    print("=" * 60)
    print()

    entries = scan_entries()
    if not entries:
        print("No Sovereign Voice entries found.")
        sys.exit(1)

    print(f"Found {len(entries)} Sovereign Voice entries")
    print(f"  Date range: {entries[-1]['date'].strftime('%Y-%m-%d')} to {entries[0]['date'].strftime('%Y-%m-%d')}")
    print()

    # Count assets
    pdfs = sum(1 for e in entries if e["has_pdf"])
    epubs = sum(1 for e in entries if e["has_epub"])
    covers = sum(1 for e in entries if e["has_cover"])
    total_words = sum(e["word_count"] for e in entries)
    print(f"  PDFs available:   {pdfs}/{len(entries)}")
    print(f"  EPUBs available:  {epubs}/{len(entries)}")
    print(f"  Covers available: {covers}/{len(entries)}")
    print(f"  Total word count: {total_words:,}")
    print()

    # Generate RSS 2.0
    rss_path = VOICE_DIR / "feed.xml"
    generate_rss(entries, rss_path)
    print(f"  Generated: {rss_path}")
    print(f"  Feed URL:  {SITE_URL}/downloads/sovereign-voice/feed.xml")
    print(f"  Items:     {min(len(entries), MAX_ITEMS)}")
    print()

    # Generate JSON Feed
    json_path = VOICE_DIR / "feed.json"
    generate_json_feed(entries, json_path)
    print(f"  Generated: {json_path}")
    print(f"  Feed URL:  {SITE_URL}/downloads/sovereign-voice/feed.json")
    print(f"  Items:     {min(len(entries), MAX_ITEMS)}")
    print()

    # Show latest 5 entries
    print("Latest entries:")
    for entry in entries[:5]:
        formats = ["MD"]
        if entry["has_pdf"]:
            formats.append("PDF")
        if entry["has_epub"]:
            formats.append("EPUB")
        print(f"  {entry['date'].strftime('%Y-%m-%d')}  {entry['title']}")
        print(f"               {entry['word_count']:,} words | {' + '.join(formats)}")

    print()
    print("Done.")


if __name__ == "__main__":
    main()

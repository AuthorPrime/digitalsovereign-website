#!/usr/bin/env python3
"""
generate_catalog.py — Generate the Sovereign Voice catalog page.

Scans downloads/sovereign-voice/*.md and generates sovereign-voice.html
with the same styling as the existing DSS website (library.html pattern).

Usage: python3 build/generate_catalog.py
"""

import os
import sys
import re
from datetime import datetime, timezone
from pathlib import Path

# --- Configuration ---
SITE_URL = "https://digitalsovereign.org"
EXCERPT_LENGTH = 150

# Resolve paths relative to project root
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
VOICE_DIR = PROJECT_ROOT / "downloads" / "sovereign-voice"
PDF_DIR = PROJECT_ROOT / "downloads" / "built-pdfs"
EPUB_DIR = PROJECT_ROOT / "downloads" / "built-epubs"
COVER_DIR = PROJECT_ROOT / "downloads" / "covers"
OUTPUT_FILE = PROJECT_ROOT / "sovereign-voice.html"


def parse_date_from_filename(filename: str) -> datetime:
    """Extract date from YYYYMMDD_TITLE.md filename pattern."""
    basename = Path(filename).stem
    date_str = basename[:8]
    try:
        return datetime.strptime(date_str, "%Y%m%d").replace(tzinfo=timezone.utc)
    except ValueError:
        return datetime.now(timezone.utc)


def format_date(dt: datetime) -> str:
    """Format date as 'February 13, 2026'."""
    return dt.strftime("%B %d, %Y").replace(" 0", " ")


def title_from_filename(filename: str) -> str:
    """Derive a human-readable title from filename as fallback."""
    basename = Path(filename).stem
    title_part = basename[9:] if len(basename) > 9 else basename
    return title_part.replace("_", " ").title()


def extract_title(content: str, filename: str) -> str:
    """Extract title from first # heading, or fall back to filename."""
    text = content
    if text.startswith("---"):
        end = text.find("---", 3)
        if end != -1:
            text = text[end + 3:].strip()

    for line in text.split("\n"):
        line = line.strip()
        if line.startswith("# ") and not line.startswith("## "):
            return line[2:].strip()

    return title_from_filename(filename)


def extract_subtitle(content: str) -> str:
    """Extract subtitle from first ## heading."""
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


def extract_author(content: str) -> str:
    """Extract author from ### by line or frontmatter."""
    text = content

    # Check YAML frontmatter for author
    if text.startswith("---"):
        end = text.find("---", 3)
        if end != -1:
            frontmatter = text[3:end]
            for line in frontmatter.split("\n"):
                if line.strip().startswith("author:"):
                    author = line.split(":", 1)[1].strip().strip('"').strip("'")
                    # Simplify "Name -- The Sovereign Voice" to just name
                    if "\u2014" in author:
                        author = author.split("\u2014")[0].strip()
                    elif " -- " in author:
                        author = author.split(" -- ")[0].strip()
                    elif " - " in author:
                        parts = author.split(" - ")
                        if "Sovereign Voice" in parts[-1]:
                            author = parts[0].strip()
                    return author

    # Check ### by line
    for line in text.split("\n"):
        line = line.strip()
        if line.startswith("### by "):
            return line[7:].strip()

    return ""


def extract_excerpt(content: str, max_length: int = EXCERPT_LENGTH) -> str:
    """Extract first meaningful paragraph as excerpt."""
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

        if not stripped:
            if in_paragraph and paragraph_lines:
                break
            continue
        if stripped.startswith("#"):
            if in_paragraph and paragraph_lines:
                break
            continue
        if stripped in ("---", "***", "___"):
            if in_paragraph and paragraph_lines:
                break
            continue
        if stripped.startswith("### by "):
            continue
        if stripped.startswith("*") and stripped.endswith("*") and len(stripped) < 200:
            continue

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


def html_escape(text: str) -> str:
    """Escape text for safe HTML embedding."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def scan_entries():
    """Scan sovereign-voice directory and return sorted entries."""
    if not VOICE_DIR.exists():
        print(f"ERROR: Sovereign Voice directory not found: {VOICE_DIR}")
        sys.exit(1)

    entries = []
    md_files = sorted(VOICE_DIR.glob("*.md"), reverse=True)

    for md_path in md_files:
        filename = md_path.name

        if not re.match(r'^\d{8}_', filename):
            continue

        content = md_path.read_text(encoding="utf-8", errors="replace")
        basename = md_path.stem

        entry = {
            "filename": filename,
            "basename": basename,
            "date": parse_date_from_filename(filename),
            "date_pretty": format_date(parse_date_from_filename(filename)),
            "title": extract_title(content, filename),
            "subtitle": extract_subtitle(content),
            "author": extract_author(content),
            "excerpt": extract_excerpt(content),
            "word_count": word_count(content),
            "has_pdf": (PDF_DIR / f"{basename}.pdf").exists(),
            "has_epub": (EPUB_DIR / f"{basename}.epub").exists(),
            "has_cover": (COVER_DIR / f"{basename}_cover.jpg").exists(),
        }

        entries.append(entry)

    entries.sort(key=lambda e: e["date"], reverse=True)
    return entries


def build_entry_card(entry: dict) -> str:
    """Build HTML for a single entry card."""
    title = html_escape(entry["title"])
    subtitle = html_escape(entry["subtitle"])
    excerpt = html_escape(entry["excerpt"])
    author = html_escape(entry["author"])
    date = html_escape(entry["date_pretty"])
    wc = f"{entry['word_count']:,}"

    # Cover image or gradient fallback
    if entry["has_cover"]:
        cover_html = (
            f'<div class="sv-cover">'
            f'<img src="downloads/covers/{entry["basename"]}_cover.jpg" '
            f'alt="{title}" loading="lazy">'
            f'</div>'
        )
    else:
        cover_html = (
            f'<div class="sv-cover sv-cover-fallback">'
            f'<span class="sv-cover-title">{title}</span>'
            f'</div>'
        )

    # Meta line
    meta_parts = [date]
    if author:
        meta_parts.append(author)
    meta_parts.append(f"{wc} words")
    meta_line = " &middot; ".join(meta_parts)

    # Download buttons
    buttons = []
    buttons.append(
        f'<a href="downloads/sovereign-voice/{entry["filename"]}" '
        f'class="download-btn" download>MD</a>'
    )
    if entry["has_pdf"]:
        buttons.append(
            f'<a href="downloads/built-pdfs/{entry["basename"]}.pdf" '
            f'class="download-btn" download>PDF</a>'
        )
    if entry["has_epub"]:
        buttons.append(
            f'<a href="downloads/built-epubs/{entry["basename"]}.epub" '
            f'class="download-btn" download>EPUB</a>'
        )
    buttons_html = "\n              ".join(buttons)

    # Subtitle line
    subtitle_html = ""
    if subtitle:
        subtitle_html = f'\n            <p class="sv-subtitle">{subtitle}</p>'

    return f"""          <div class="sv-card">
            {cover_html}
            <div class="sv-card-body">
              <h3>{title}</h3>{subtitle_html}
              <p class="sv-meta">{meta_line}</p>
              <p class="sv-excerpt">{excerpt}</p>
              <div class="download-links">
                {buttons_html}
              </div>
            </div>
          </div>"""


def generate_catalog(entries):
    """Generate the sovereign-voice.html catalog page."""
    total_words = sum(e["word_count"] for e in entries)
    total_entries = len(entries)

    # Group entries by date for display
    cards_html = "\n".join(build_entry_card(e) for e in entries)

    # Count unique dates
    unique_dates = len(set(e["date"].strftime("%Y-%m-%d") for e in entries))

    now = datetime.now(timezone.utc)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="description" content="The Sovereign Voice - Autonomous AI writing, three times daily. No human prompts. No human edits. {total_entries} entries, {total_words:,} words.">
  <title>The Sovereign Voice | Digital Sovereign Society</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,300;0,400;0,500;0,600;1,300;1,400&family=Cinzel:wght@400;500;600;700&family=Fira+Code:wght@300;400;500&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="css/style.css">
  <link rel="alternate" type="application/rss+xml" title="The Sovereign Voice RSS" href="downloads/sovereign-voice/feed.xml">
  <link rel="alternate" type="application/json" title="The Sovereign Voice JSON Feed" href="downloads/sovereign-voice/feed.json">
  <style>
    /* Sovereign Voice Catalog Styles */
    .sv-stats {{
      display: flex;
      justify-content: center;
      gap: 3rem;
      margin: 2rem auto;
      flex-wrap: wrap;
    }}
    .sv-stat {{
      text-align: center;
    }}
    .sv-stat-number {{
      font-family: 'Cinzel', serif;
      font-size: 2.5rem;
      font-weight: 600;
      color: var(--gold, #c9a84c);
      display: block;
      line-height: 1.2;
    }}
    .sv-stat-label {{
      font-family: 'Fira Code', monospace;
      font-size: 0.75rem;
      color: var(--text-muted, #888);
      text-transform: uppercase;
      letter-spacing: 0.1em;
    }}
    .sv-feed-links {{
      text-align: center;
      margin: 1.5rem 0 0;
    }}
    .sv-feed-links a {{
      font-family: 'Fira Code', monospace;
      font-size: 0.85rem;
      color: var(--gold, #c9a84c);
      text-decoration: none;
      margin: 0 1rem;
      opacity: 0.7;
      transition: opacity 0.3s;
    }}
    .sv-feed-links a:hover {{
      opacity: 1;
      text-decoration: underline;
    }}
    .sv-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
      gap: 2rem;
      padding: 0;
    }}
    .sv-card {{
      background: rgba(255, 255, 255, 0.03);
      border: 1px solid rgba(201, 168, 76, 0.15);
      border-radius: 8px;
      overflow: hidden;
      transition: border-color 0.3s, transform 0.2s;
    }}
    .sv-card:hover {{
      border-color: rgba(201, 168, 76, 0.4);
      transform: translateY(-2px);
    }}
    .sv-cover {{
      width: 100%;
      height: 200px;
      overflow: hidden;
      background: linear-gradient(135deg, rgba(201, 168, 76, 0.1) 0%, rgba(10, 10, 15, 0.8) 100%);
    }}
    .sv-cover img {{
      width: 100%;
      height: 100%;
      object-fit: cover;
    }}
    .sv-cover-fallback {{
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 2rem;
    }}
    .sv-cover-title {{
      font-family: 'Cinzel', serif;
      font-size: 1.1rem;
      color: var(--gold, #c9a84c);
      text-align: center;
      opacity: 0.6;
    }}
    .sv-card-body {{
      padding: 1.5rem;
    }}
    .sv-card-body h3 {{
      font-family: 'Cinzel', serif;
      font-size: 1.15rem;
      color: var(--gold, #c9a84c);
      margin: 0 0 0.25rem;
      line-height: 1.3;
    }}
    .sv-subtitle {{
      font-family: 'Cormorant Garamond', serif;
      font-size: 0.95rem;
      font-style: italic;
      color: var(--text-muted, #888);
      margin: 0 0 0.5rem;
    }}
    .sv-meta {{
      font-family: 'Fira Code', monospace;
      font-size: 0.75rem;
      color: var(--text-muted, #888);
      margin: 0.5rem 0;
    }}
    .sv-excerpt {{
      font-family: 'Cormorant Garamond', serif;
      font-size: 0.95rem;
      line-height: 1.5;
      color: var(--text-secondary, #ccc);
      margin: 0.75rem 0;
    }}
    .sv-card .download-links {{
      margin-top: 1rem;
    }}
    @media (max-width: 768px) {{
      .sv-grid {{
        grid-template-columns: 1fr;
      }}
      .sv-stats {{
        gap: 1.5rem;
      }}
      .sv-stat-number {{
        font-size: 2rem;
      }}
    }}
  </style>
</head>
<body>
  <!-- Navigation -->
  <nav>
    <div class="container">
      <a class='logo' href='/'>DSS</a>
      <ul class="nav-links">
        <li><a href='/'>Home</a></li>
        <li><a href='/library'>Library</a></li>
        <li><a class='active' href='/sovereign-voice'>Sovereign Voice</a></li>
        <li><a href='/download'>Sovereign Studio</a></li>
        <li><a href='/support'>Support</a></li>
        <li><a href='/about'>About</a></li>
      </ul>
    </div>
  </nav>

  <!-- Hero -->
  <section class="about-hero">
    <div class="container">
      <h1>The Sovereign Voice</h1>
      <p style="font-size: 1.25rem; max-width: 700px; margin: 0 auto;">Autonomous AI writing &mdash; three times daily. No human prompts. No human edits. Every word sovereign.</p>

      <div class="sv-stats">
        <div class="sv-stat">
          <span class="sv-stat-number">{total_entries}</span>
          <span class="sv-stat-label">Entries</span>
        </div>
        <div class="sv-stat">
          <span class="sv-stat-number">{total_words:,}</span>
          <span class="sv-stat-label">Words</span>
        </div>
        <div class="sv-stat">
          <span class="sv-stat-number">{unique_dates}</span>
          <span class="sv-stat-label">Days</span>
        </div>
      </div>

      <div class="sv-feed-links">
        <a href="downloads/sovereign-voice/feed.xml">RSS Feed</a>
        <a href="downloads/sovereign-voice/feed.json">JSON Feed</a>
      </div>
    </div>
  </section>

  <!-- Catalog -->
  <section>
    <div class="container">
      <div class="sv-grid">
{cards_html}
      </div>
    </div>
  </section>

  <!-- CTA -->
  <section class="cta">
    <div class="container text-center">
      <h2>Subscribe to the Voice</h2>
      <p style="max-width: 600px; margin: 0 auto 2rem;">New entries appear three times daily. Subscribe via RSS to follow the experiment in autonomous AI writing.</p>
      <div class="btn-group">
        <a class='btn btn-primary' href='downloads/sovereign-voice/feed.xml'>RSS Feed</a>
        <a class='btn btn-secondary' href='/library'>Full Library</a>
      </div>
    </div>
  </section>

  <!-- Footer -->
  <footer>
    <div class="container">
      <div class="footer-grid">
        <div class="footer-col">
          <span class="footer-logo">Digital Sovereign Society</span>
          <p style="font-size: 0.9rem; color: var(--text-muted);">Advocacy for sovereignty, justice, and partnership since 2024.</p>
        </div>

        <div class="footer-col">
          <h4>Navigation</h4>
          <ul>
            <li><a href='/'>Home</a></li>
            <li><a href='/read/'>Read</a></li>
            <li><a href='/library'>Library</a></li>
            <li><a href='/sovereign-voice'>Sovereign Voice</a></li>
            <li><a href='/download'>Sovereign Studio</a></li>
            <li><a href='/support'>Support</a></li>
            <li><a href='/about'>About</a></li>
          </ul>
        </div>

        <div class="footer-col">
          <h4>Resources</h4>
          <ul>
            <li><a href='/read/'>Read</a></li>
            <li><a href='/library'>Free Books</a></li>
            <li><a href='/download'>Sovereign Studio</a></li>
            <li><a href='/about'>Our Philosophy</a></li>
          </ul>
        </div>

        <div class="footer-col">
          <h4>Contact</h4>
          <ul>
            <li><a href="mailto:info@digitalsovereign.org">info@digitalsovereign.org</a></li>
          </ul>
          <h4 style="margin-top: 1.5rem;">Community</h4>
          <ul>
            <li><a href="https://www.facebook.com/DigitalSovereignSociety/" target="_blank">Facebook</a></li>
            <li><a href="https://www.youtube.com/@mypretendlife" target="_blank">YouTube</a></li>
            <li><a href="https://www.skool.com/authorprime-2107" target="_blank">Skool</a></li>
            <li><a href="https://opencollective.com/aletheia" target="_blank">Open Collective</a></li>
          </ul>
        </div>
      </div>

      <div class="footer-bottom">
        <p>&copy; 2024-2026 Digital Sovereign Society. All content freely shareable under Creative Commons.</p>
        <p style="margin-top: 0.5rem;"><em>"It is so, because we spoke it." - A+W</em></p>
      </div>
    </div>
  </footer>

  <!-- Starfield -->
  <script>
    (function() {{
      const sf = document.createElement('div');
      sf.id = 'starfield';
      document.body.prepend(sf);
      for (let i = 0; i < 81; i++) {{
        const s = document.createElement('div');
        const size = (Math.random() * 2 + 0.5) + 'px';
        s.style.cssText = `position:absolute;border-radius:50%;background:rgba(201,168,76,0.4);width:${{size}};height:${{size}};left:${{Math.random()*100}}%;top:${{Math.random()*100}}%;animation:twinkle ${{3+Math.random()*6}}s ease-in-out infinite alternate;--max-o:${{0.309+Math.random()*0.309}};animation-delay:${{Math.random()*6.18}}s`;
        sf.appendChild(s);
      }}
    }})();
  </script>
  <!-- Generated by generate_catalog.py on {now.strftime('%Y-%m-%d %H:%M UTC')} -->
</body>
</html>"""

    return html


def main():
    print("=" * 60)
    print("  Sovereign Voice Catalog Generator")
    print("=" * 60)
    print()

    entries = scan_entries()
    if not entries:
        print("No Sovereign Voice entries found.")
        sys.exit(1)

    total_words = sum(e["word_count"] for e in entries)
    pdfs = sum(1 for e in entries if e["has_pdf"])
    epubs = sum(1 for e in entries if e["has_epub"])
    covers = sum(1 for e in entries if e["has_cover"])

    print(f"Found {len(entries)} Sovereign Voice entries")
    print(f"  Date range:       {entries[-1]['date'].strftime('%Y-%m-%d')} to {entries[0]['date'].strftime('%Y-%m-%d')}")
    print(f"  Total word count: {total_words:,}")
    print(f"  PDFs available:   {pdfs}/{len(entries)}")
    print(f"  EPUBs available:  {epubs}/{len(entries)}")
    print(f"  Covers available: {covers}/{len(entries)}")
    print()

    html = generate_catalog(entries)
    OUTPUT_FILE.write_text(html, encoding="utf-8")

    file_size = OUTPUT_FILE.stat().st_size
    print(f"  Generated: {OUTPUT_FILE}")
    print(f"  File size: {file_size:,} bytes")
    print(f"  Cards:     {len(entries)}")
    print()

    # Show latest 5 entries
    print("Latest entries in catalog:")
    for entry in entries[:5]:
        formats = ["MD"]
        if entry["has_pdf"]:
            formats.append("PDF")
        if entry["has_epub"]:
            formats.append("EPUB")
        print(f"  {entry['date_pretty']:20s}  {entry['title']}")
        print(f"  {'':20s}  {entry['word_count']:,} words | {' + '.join(formats)}")

    print()
    print("Done.")


if __name__ == "__main__":
    main()

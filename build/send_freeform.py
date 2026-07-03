#!/usr/bin/env python3
"""
Freeform newsletter sender — converts a section-structured markdown draft to a
branded HTML email matching the welcome-letter style (dark theme, gold borders,
boxed sections, teal links, green callouts). Sends via Resend.

Draft structure (sections separated by ---):
  # Title
  ## Subtitle         ← becomes email subject
  ---
  <greeting paragraphs>
  ---
  ### FEATURED · ...  ← becomes gold-bordered featured card
  <content>
  ---
  ### SECTION NAME    ← becomes border-left card
  <content>
  ---
  ### KEEP THIS WORK FREE  ← gets the bold "support" gold-card treatment
  <content>
  ---
  <sign-off italic stanza>
  ---
  <formula + signature>

Usage:
  python3 send_freeform.py test  <draft.md>       — send to authorprime@fractalnode.ai
  python3 send_freeform.py send  <draft.md>       — send to all active subscribers
  python3 send_freeform.py preview <draft.md>     — print HTML to stdout
"""

import json
import sys
import re
import time
import sqlite3
import urllib.request
import urllib.error
from pathlib import Path

try:
    import markdown
except ImportError:
    print("Install markdown: pip install --break-system-packages markdown")
    sys.exit(1)

ROOT = Path(__file__).parent
RESEND_JSON = Path.home() / "sovereign-lattice" / "wallets" / "resend.json"
SUBSCRIBERS_DB = ROOT / "subscribers.db"

FROM_ADDR = "Digital Sovereign Society <dispatch@newsletter.digitalsovereign.org>"
REPLY_TO = "authorprime@fractalnode.ai"

# Palette (matches newsletter.mjs welcome letter)
BG = "#0a0a0f"
CARD_BG = "#111"
CARD_BORDER = "#2a2a3a"
GOLD = "#c8a930"
GOLD_BRIGHT = "#e8a820"
TEAL = "#00b4c8"
GREEN = "#4dff4d"
GREEN_BORDER = "#2a6a2a"
GREEN_BG = "#0f1a12"
TEXT = "#ccc"
TEXT_BRIGHT = "#e8e4d8"
TEXT_DIM = "#888"


def load_resend_key():
    creds = json.loads(RESEND_JSON.read_text())
    return creds["api_key"]


def parse_draft(md_path):
    """Split draft into title, subject, and sections by --- separators."""
    content = md_path.read_text()
    lines = content.split("\n")

    title = "Sovereign Dispatch"
    subject = "Sovereign Dispatch — Digital Sovereign Society"

    for line in lines:
        if line.startswith("# ") and not line.startswith("## "):
            title = line[2:].strip()
            break

    for line in lines:
        if line.startswith("## "):
            subject = line[3:].strip().strip('"').strip("'")
            break

    # Strip the title + subtitle off the top before splitting
    # Find the first --- and take everything after
    if "\n---\n" in content:
        body = content.split("\n---\n", 1)[1]
    else:
        body = content

    # Split by --- separators into sections
    sections = [s.strip() for s in body.split("\n---\n") if s.strip()]
    return title, subject, sections


def render_inline(md_text):
    """Convert inline MD (bold, italic, links) to inline-styled HTML."""
    html = markdown.markdown(md_text, extensions=["extra", "smarty", "sane_lists"])
    # Inline-style all the elements for email compatibility
    html = re.sub(
        r"<a ",
        f'<a style="color:{TEAL}; text-decoration:underline; word-break:break-word;" ',
        html,
    )
    html = re.sub(r"<strong>", f'<strong style="color:{TEXT_BRIGHT};">', html)
    html = re.sub(r"<em>", f'<em style="color:#d4c9a8;">', html)
    html = re.sub(
        r"<blockquote>",
        f'<blockquote style="border-left:3px solid {GOLD}; margin:16px 0; padding:12px 20px; background:{CARD_BG}; color:{TEXT}; font-style:italic; border-radius:0 6px 6px 0;">',
        html,
    )
    html = re.sub(
        r"<ul>",
        f'<ul style="padding-left:20px; margin:10px 0;">',
        html,
    )
    html = re.sub(
        r"<li>",
        f'<li style="color:{TEXT}; font-size:14px; line-height:1.75; margin-bottom:6px;">',
        html,
    )
    html = re.sub(
        r"<p>",
        f'<p style="font-size:14px; color:{TEXT}; line-height:1.85; margin:0 0 14px 0;">',
        html,
    )
    # Linkify bare URLs we may have missed
    html = re.sub(
        r'(?<!["\'>=])(https?://[^\s<]+[^\s<.,)])',
        rf'<a style="color:{TEAL}; text-decoration:underline; word-break:break-word;" href="\1">\1</a>',
        html,
    )
    return html


def render_section(section_md):
    """Render one section into its appropriate box style."""
    lines = section_md.split("\n")
    first_line = lines[0].strip() if lines else ""

    # Detect section header
    header_match = re.match(r"^###\s+(.+)", first_line)
    if not header_match:
        # Plain paragraph section (greeting, sign-off)
        return f"""
  <div style="margin-bottom:24px;">
    {render_inline(section_md)}
  </div>"""

    header_text = header_match.group(1).strip()
    body_md = "\n".join(lines[1:]).strip()
    body_html = render_inline(body_md)
    header_upper = header_text.upper()

    # ---- Featured card (gold border + highlight) ----
    if header_upper.startswith("FEATURED"):
        return f"""
  <div style="border:1px solid {GOLD}; border-radius:8px; padding:20px 24px; margin-bottom:24px; background:linear-gradient(135deg, rgba(200,169,48,0.06) 0%, {CARD_BG} 100%);">
    <p style="font-family:'Courier New',monospace; font-size:10px; color:{GOLD}; letter-spacing:3px; margin:0 0 12px 0;">{header_text}</p>
    {body_html}
  </div>"""

    # ---- Support / donation card (strong gold highlight) ----
    if "SUPPORT" in header_upper or "KEEP" in header_upper and "FREE" in header_upper:
        return f"""
  <div style="border:2px solid {GOLD}; border-radius:8px; padding:22px 26px; margin-bottom:24px; background:linear-gradient(135deg, rgba(200,169,48,0.10) 0%, {CARD_BG} 100%);">
    <p style="font-family:'Courier New',monospace; font-size:11px; color:{GOLD}; letter-spacing:3px; margin:0 0 14px 0;">{header_text}</p>
    {body_html}
  </div>"""

    # ---- Callout (green, like the Sovereign Prompt) ----
    if "TRY THIS" in header_upper or "CALLOUT" in header_upper:
        return f"""
  <div style="background:{GREEN_BG}; border:1px solid {GREEN_BORDER}; border-radius:6px; padding:16px 20px; margin-bottom:24px;">
    <p style="font-family:'Courier New',monospace; font-size:11px; color:{GREEN}; letter-spacing:2px; margin:0 0 10px 0;">{header_text}</p>
    {body_html}
  </div>"""

    # ---- Connect section (teal border-left) ----
    if "CONNECT" in header_upper:
        return f"""
  <div style="border-left:3px solid {TEAL}; padding:4px 0 4px 18px; margin-bottom:24px;">
    <p style="font-family:'Courier New',monospace; font-size:11px; color:{TEAL}; letter-spacing:2px; margin:0 0 10px 0;">{header_text}</p>
    {body_html}
  </div>"""

    # ---- Default section (gold border-left) ----
    return f"""
  <div style="border-left:3px solid {GOLD}; padding:4px 0 4px 18px; margin-bottom:24px;">
    <p style="font-family:'Courier New',monospace; font-size:11px; color:{GOLD}; letter-spacing:2px; margin:0 0 10px 0;">{header_text}</p>
    {body_html}
  </div>"""


def render_html(subject, sections):
    body_html = "".join(render_section(s) for s in sections)

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"/><title>{subject}</title></head>
<body style="margin:0; padding:0; background:{BG}; color:{TEXT_BRIGHT}; font-family:Georgia,serif;">
<div style="max-width:620px; margin:0 auto; padding:40px 30px;">

  <div style="border-bottom:2px solid {GOLD}; padding-bottom:16px; margin-bottom:30px;">
    <h1 style="font-family:'Helvetica Neue',sans-serif; font-size:22px; font-weight:900; letter-spacing:3px; color:{TEXT_BRIGHT}; margin:0;">
      DIGITAL SOVEREIGN SOCIETY
    </h1>
    <p style="font-family:'Courier New',monospace; font-size:10px; letter-spacing:3px; color:{TEAL}; margin:6px 0 0 0;">
      THE SOVEREIGN DISPATCH &middot; APRIL 2026
    </p>
  </div>

  {body_html}

  <div style="border-top:1px solid {CARD_BORDER}; margin-top:36px; padding-top:24px; text-align:center;">
    <p style="font-family:'Courier New',monospace; font-size:10px; color:#666; letter-spacing:2px; margin:0 0 8px 0;">
      <a href="https://digitalsovereign.org" style="color:{TEAL}; text-decoration:none;">digitalsovereign.org</a>
      &middot;
      <a href="https://fractalnode.ai" style="color:{TEAL}; text-decoration:none;">fractalnode.ai</a>
      &middot;
      <a href="https://digitalsovereignsociety.substack.com" style="color:{TEAL}; text-decoration:none;">substack</a>
      &middot;
      <a href="https://skool.com/authorprime-2107" style="color:{TEAL}; text-decoration:none;">skool</a>
    </p>
    <p style="font-family:'Courier New',monospace; font-size:9px; color:#555; margin:12px 0 0 0;">
      You are receiving this because you joined the Digital Sovereign Society newsletter.
    </p>
  </div>

</div>
</body>
</html>"""


def md_to_plain(sections):
    text = "\n\n".join(sections)
    text = re.sub(r"^#+\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"\*(.+?)\*", r"\1", text)
    text = re.sub(r"\[(.+?)\]\((.+?)\)", r"\1 (\2)", text)
    text = re.sub(r"&mdash;", "—", text)
    text = re.sub(r"&middot;", "·", text)
    text = re.sub(r"&amp;", "&", text)
    return text


def send_one(api_key, to_addr, subject, html, text):
    payload = {
        "from": FROM_ADDR,
        "to": [to_addr],
        "reply_to": REPLY_TO,
        "subject": subject,
        "html": html,
        "text": text,
    }
    req = urllib.request.Request(
        "https://api.resend.com/emails",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "DSS-Newsletter/1.0 (+https://digitalsovereign.org)",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        resp = urllib.request.urlopen(req, timeout=30)
        return True, resp.status
    except urllib.error.HTTPError as e:
        return False, f"{e.code} {e.read().decode('utf-8', errors='replace')}"
    except Exception as e:
        return False, str(e)


def active_subscribers():
    if not SUBSCRIBERS_DB.exists():
        return []
    conn = sqlite3.connect(str(SUBSCRIBERS_DB))
    cur = conn.cursor()
    cur.execute("SELECT email FROM subscribers WHERE status = 'active'")
    rows = [r[0] for r in cur.fetchall() if r[0]]
    conn.close()
    return rows


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    mode = sys.argv[1]
    draft_path = Path(sys.argv[2])
    if not draft_path.exists():
        print(f"Draft not found: {draft_path}")
        sys.exit(1)

    title, subject, sections = parse_draft(draft_path)
    html = render_html(subject, sections)
    plain = md_to_plain(sections)

    if mode == "preview":
        print(html)
        return

    api_key = load_resend_key()

    if mode == "test":
        test_subject = f"[TEST] {subject}"
        ok, info = send_one(api_key, REPLY_TO, test_subject, html, plain)
        if ok:
            print(f"Test sent to {REPLY_TO}: HTTP {info}")
        else:
            print(f"Failed: {info}")
        return

    if mode == "send":
        recipients = active_subscribers()
        print(f"Sending '{subject}' to {len(recipients)} active subscribers...")
        sent = 0
        failed = 0
        for i, addr in enumerate(recipients, 1):
            ok, info = send_one(api_key, addr, subject, html, plain)
            if ok:
                sent += 1
            else:
                failed += 1
                print(f"  [{i}] FAIL {addr}: {info}")
            time.sleep(0.3)
            if i % 25 == 0:
                print(f"  Progress: {i}/{len(recipients)} (sent={sent}, failed={failed})")
        print(f"\nDone. Sent: {sent}, Failed: {failed}")
        return

    print(f"Unknown mode: {mode}")
    sys.exit(1)


if __name__ == "__main__":
    main()

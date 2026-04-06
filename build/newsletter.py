#!/usr/bin/env python3
"""
Newsletter workflow tool for Digital Sovereign Society + FractalNode.

Usage:
  python3 newsletter.py subscribers    — List all newsletter subscribers (both sites)
  python3 newsletter.py customers      — List Stripe customers (buyers + donors)
  python3 newsletter.py everyone       — Combined deduped list: subscribers + customers
  python3 newsletter.py draft          — Generate this week's newsletter draft
  python3 newsletter.py export         — Export all unique emails (one per line)
  python3 newsletter.py send <file>    — Send a newsletter to all subscribers (Gmail)
  python3 newsletter.py send-resend <f> — Send via Resend API (recommended)
  python3 newsletter.py send-test <f>  — Send to authorprime@ only (preview)
  python3 newsletter.py sync           — Pull new signups from Netlify into local DB
  python3 newsletter.py status         — Show subscriber count and recent signups
  python3 newsletter.py help           — Show this help

Requires:
  NETLIFY_TOKEN env var or ~/.netlify/config.json
  STRIPE_SECRET_KEY env var or build/.stripe_key (for customer list)
  SMTP credentials: ~/sovereign-lattice/wallets/smtp.json
"""

import json
import os
import sys
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime, timedelta
from pathlib import Path
import urllib.request
import urllib.error
import re

# Site IDs
DSS_SITE_ID = "999ba04e-37d4-4db2-9f52-8ea60380c94a"
FN_SITE_ID = "dffe1374-cd27-44ec-b436-57cfe30925dd"

DRAFTS_DIR = Path(__file__).parent.parent.parent / "sovereign-lattice" / "drafts"
NEWSLETTER_DIR = DRAFTS_DIR / "newsletters"
CREDS_DIR = Path(__file__).parent
SMTP_JSON = Path.home() / "sovereign-lattice" / "wallets" / "smtp.json"
UNSUBSCRIBE_FILE = CREDS_DIR / "unsubscribed.txt"

# FractalNode Magazine research path
FN_MAGAZINE = Path("/mnt/c/Users/Author Prime/Desktop/Digital-Sovereign-Society/FractalNode-Magazine")

# ─────────────────────────────────────────────
# Credentials
# ─────────────────────────────────────────────

def get_netlify_token():
    """Get Netlify auth token from env or config file."""
    token = os.environ.get("NETLIFY_TOKEN")
    if token:
        return token
    config_path = Path.home() / ".netlify" / "config.json"
    if config_path.exists():
        try:
            config = json.loads(config_path.read_text())
            for user_data in config.get("users", {}).values():
                t = user_data.get("auth", {}).get("token")
                if t:
                    return t
        except (json.JSONDecodeError, KeyError):
            pass
    return None


def get_stripe_key():
    """Get Stripe secret key from env or file."""
    key = os.environ.get("STRIPE_SECRET_KEY")
    if key:
        return key
    key_file = CREDS_DIR / ".stripe_key"
    if key_file.exists():
        return key_file.read_text().strip()
    return None


def get_smtp_credentials():
    """Get SMTP credentials from smtp.json."""
    # Primary: sovereign-lattice/wallets/smtp.json
    if SMTP_JSON.exists():
        try:
            data = json.loads(SMTP_JSON.read_text())
            return {
                "user": data["user"],
                "password": data["pass"],
                "host": data.get("host", "smtp.gmail.com"),
                "port": data.get("port", 587),
            }
        except (json.JSONDecodeError, KeyError):
            pass
    # Fallback: env vars
    user = os.environ.get("SMTP_USER")
    password = os.environ.get("SMTP_PASS")
    if user and password:
        return {"user": user, "password": password, "host": "smtp.gmail.com", "port": 587}
    return None


def get_unsubscribed():
    """Load unsubscribe list."""
    if UNSUBSCRIBE_FILE.exists():
        return set(
            line.strip().lower()
            for line in UNSUBSCRIBE_FILE.read_text().splitlines()
            if line.strip() and not line.startswith("#")
        )
    return set()


# ─────────────────────────────────────────────
# API helpers
# ─────────────────────────────────────────────

def netlify_api(endpoint):
    """Call Netlify API."""
    token = get_netlify_token()
    if not token:
        return None
    req = urllib.request.Request(
        f"https://api.netlify.com/api/v1/{endpoint}",
        headers={"Authorization": f"Bearer {token}"}
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except Exception as e:
        print(f"  Netlify API error: {e}")
        return None


def stripe_api(endpoint):
    """Call Stripe API."""
    import base64
    key = get_stripe_key()
    if not key:
        return None
    auth = base64.b64encode(f"{key}:".encode()).decode()
    req = urllib.request.Request(
        f"https://api.stripe.com/v1/{endpoint}",
        headers={"Authorization": f"Basic {auth}"}
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except Exception as e:
        print(f"  Stripe API error: {e}")
        return None


# ─────────────────────────────────────────────
# Data sources
# ─────────────────────────────────────────────

def get_site_form_subscribers(site_id, form_name, source_label):
    """Get form submissions from a Netlify site."""
    forms = netlify_api(f"sites/{site_id}/forms") or []
    target_form = None
    for form in forms:
        if form.get("name") == form_name:
            target_form = form
            break
    if not target_form:
        return []

    form_id = target_form["id"]
    submissions = netlify_api(f"forms/{form_id}/submissions") or []
    subscribers = []
    for sub in submissions:
        data = sub.get("data", {})
        email = data.get("email", "").strip()
        if email:
            subscribers.append({
                "email": email,
                "name": data.get("name", ""),
                "date": sub.get("created_at", "")[:10],
                "source": source_label,
            })
    return subscribers


def get_blob_subscribers(site_id, store_name="newsletter-subscribers"):
    """Get subscribers stored in Netlify Blobs (where the serverless function writes them)."""
    token = get_netlify_token()
    if not token:
        return []

    subscribers = []
    try:
        # List all blobs in the store
        url = f"https://api.netlify.com/api/v1/blobs/{site_id}/{store_name}"
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read())

        blobs = data.get("blobs", [])
        for blob in blobs:
            key = blob.get("key", "")
            # Fetch each blob's content
            try:
                blob_url = f"https://api.netlify.com/api/v1/blobs/{site_id}/{store_name}/{key}"
                req2 = urllib.request.Request(blob_url, headers={"Authorization": f"Bearer {token}"})
                with urllib.request.urlopen(req2) as resp2:
                    entry = json.loads(resp2.read())
                    email = entry.get("email", "").strip()
                    if email:
                        subscribers.append({
                            "email": email,
                            "name": entry.get("name", ""),
                            "date": entry.get("subscribed_at", "")[:10],
                            "source": f"blob-{entry.get('source', 'website')}",
                        })
            except Exception as e:
                print(f"    Blob read error for {key}: {e}")
                continue

        print(f"  Found {len(subscribers)} subscribers in Blobs store '{store_name}'")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            print(f"  Blobs store '{store_name}' not found (no signups yet via function)")
        else:
            print(f"  Blobs API error: {e.code} {e.reason}")
    except Exception as e:
        print(f"  Blobs sync error: {e}")

    return subscribers


def get_subscribers():
    """Get all newsletter subscribers from Netlify Blobs + Forms + Stripe."""
    # Primary source: Netlify Blobs (where the serverless function stores signups)
    print("  Pulling from Netlify Blobs (primary)...")
    blob_subs = get_blob_subscribers(DSS_SITE_ID, "newsletter-subscribers")

    # Legacy source: Netlify Forms (older signups may be here)
    print("  Pulling from Netlify Forms (legacy)...")
    dss_subs = get_site_form_subscribers(DSS_SITE_ID, "newsletter", "dss-newsletter")
    fn_subs = get_site_form_subscribers(FN_SITE_ID, "subscribe", "fractalnode")

    # Also pull Stripe customers (people who bought but may not have signed up)
    print("  Pulling from Stripe customers...")
    stripe_subs = get_stripe_customers()

    all_subs = blob_subs + dss_subs + fn_subs
    # Add Stripe customers as subscribers too
    for sc in stripe_subs:
        all_subs.append({
            "email": sc.get("email", ""),
            "name": sc.get("name", ""),
            "date": sc.get("date", ""),
            "source": "stripe-customer",
        })

    # Deduplicate by email
    seen = set()
    deduped = []
    for s in all_subs:
        email = s.get("email", "").lower().strip()
        if email and email not in seen:
            seen.add(email)
            deduped.append(s)

    print(f"  Total: {len(blob_subs)} blobs + {len(dss_subs)} DSS forms + {len(fn_subs)} FN forms + {len(stripe_subs)} Stripe = {len(deduped)} unique")
    return deduped


def get_stripe_customers():
    """Get customers from Stripe (people who bought or donated)."""
    key = get_stripe_key()
    if not key:
        return []

    data = stripe_api("checkout/sessions?limit=100&status=complete")
    if not data:
        return []

    customers = []
    seen = set()
    for session in data.get("data", []):
        email = (session.get("customer_details") or {}).get("email", "")
        name = (session.get("customer_details") or {}).get("name", "")
        if email and email not in seen:
            seen.add(email)
            amount = session.get("amount_total", 0) / 100
            customers.append({
                "email": email,
                "name": name,
                "date": datetime.fromtimestamp(session.get("created", 0)).strftime("%Y-%m-%d"),
                "source": f"stripe (${amount:.0f})",
            })
    return customers


def get_everyone():
    """Combined deduplicated list of subscribers + customers + local DB, minus unsubscribed."""
    subs = get_subscribers()
    custs = get_stripe_customers()
    unsubscribed = get_unsubscribed()

    # Also pull from local subscriber database if available
    db_subs = []
    try:
        from subscribers import get_active_subscribers, get_unsubscribed_emails
        db_subs = get_active_subscribers()
        # Merge DB unsubscribed/bounced into the unsubscribe set
        unsubscribed = unsubscribed | get_unsubscribed_emails()
        print(f"  Loaded {len(db_subs)} subscribers from local DB")
    except ImportError:
        pass
    except Exception as e:
        print(f"  Warning: Could not read subscriber DB: {e}")

    seen = {}
    for person in subs + custs + db_subs:
        email = person["email"].lower().strip()
        if email in unsubscribed:
            continue
        if email not in seen:
            seen[email] = person
        else:
            existing = seen[email]
            if person["date"] and (not existing["date"] or person["date"] < existing["date"]):
                existing["date"] = person["date"]
            if person["source"] not in existing["source"]:
                existing["source"] += f" + {person['source']}"
            if not existing["name"] and person["name"]:
                existing["name"] = person["name"]

    return list(seen.values())


# ─────────────────────────────────────────────
# HTML email builder
# ─────────────────────────────────────────────

def build_weekly_html(subject, sections, first_name="friend"):
    """Build branded HTML email for weekly dispatch."""
    # Build investigation cards
    investigation_html = ""
    for item in sections.get("investigations", []):
        investigation_html += f"""
  <div style="background:#111; border:1px solid #2a2a3a; border-radius:6px; padding:16px 20px; margin-bottom:10px;">
    <p style="font-size:13px; font-weight:bold; color:#e8e4d8; margin:0 0 4px 0;">{item['title']}</p>
    <p style="font-size:13px; color:#d0ccc0; line-height:1.7; margin:0;">{item['blurb']}</p>
  </div>"""

    # Build news items
    news_html = ""
    for item in sections.get("news", []):
        news_html += f"""
    <li style="font-size:13px; color:#ccc; line-height:1.8; margin-bottom:6px;">{item}</li>"""

    # Build the full email
    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"/></head>
<body style="margin:0; padding:0; background:#0a0a0f; color:#e8e4d8; font-family:Georgia,serif;">
<div style="max-width:600px; margin:0 auto; padding:40px 30px;">

  <div style="border-bottom:2px solid #c8a930; padding-bottom:16px; margin-bottom:30px;">
    <h1 style="font-family:'Helvetica Neue',sans-serif; font-size:22px; font-weight:900; letter-spacing:3px; color:#e8e4d8; margin:0;">
      THE WEEKLY DISPATCH
    </h1>
    <p style="font-family:'Courier New',monospace; font-size:10px; letter-spacing:3px; color:#00b4c8; margin:6px 0 0 0;">
      DIGITAL SOVEREIGN SOCIETY &middot; FRACTALNODE
    </p>
  </div>

  <p style="font-size:16px; color:#e8e4d8; margin-bottom:20px;">
    Hey {first_name},
  </p>

  <p style="font-size:14px; color:#ccc; line-height:1.8; margin-bottom:24px;">
    {sections.get('intro', 'Here is what happened this week.')}
  </p>

  {f'''
  <div style="border-left:3px solid #c8a930; padding-left:16px; margin-bottom:24px;">
    <p style="font-family:'Courier New',monospace; font-size:11px; color:#c8a930; letter-spacing:2px; margin:0 0 8px 0;">FROM THE INVESTIGATIONS</p>
  </div>
  {investigation_html}
  <p style="font-family:'Courier New',monospace; font-size:10px; color:#c8a930; letter-spacing:1px; margin:16px 0 28px 0; text-align:center;">
    EVERY CLAIM SOURCED &middot; SPECULATION MARKED &middot; RECEIPTS ATTACHED
  </p>
  ''' if investigation_html else ''}

  {f'''
  <div style="border-left:3px solid #00b4c8; padding-left:16px; margin-bottom:24px;">
    <p style="font-family:'Courier New',monospace; font-size:11px; color:#00b4c8; letter-spacing:2px; margin:0 0 8px 0;">AI RIGHTS &amp; DIGITAL SOVEREIGNTY</p>
    <ul style="padding-left:16px; margin:0;">
      {news_html}
    </ul>
  </div>
  ''' if news_html else ''}

  {f'''
  <div style="background:#0a1520; border:1px solid #1a3a5a; border-radius:6px; padding:20px; margin-bottom:24px;">
    <p style="font-family:'Courier New',monospace; font-size:10px; color:#4d9fff; letter-spacing:2px; margin:0 0 8px 0;">FRACTALNODE MAGAZINE</p>
    <p style="font-size:14px; color:#e8e4d8; line-height:1.7; margin:0;">{sections['magazine']}</p>
    <a href="https://fractalnode.ai/magazine" style="display:inline-block; margin-top:10px; font-family:'Courier New',monospace; font-size:12px; color:#00b4c8; text-decoration:none;">READ &rarr;</a>
  </div>
  ''' if sections.get('magazine') else ''}

  {f'''
  <div style="background:#111; border-left:3px solid #4dff4d; padding:16px 20px; margin-bottom:24px;">
    <p style="font-family:'Courier New',monospace; font-size:10px; color:#4dff4d; letter-spacing:2px; margin:0 0 8px 0;">ONE THOUGHT</p>
    <p style="font-size:14px; font-style:italic; color:#e8e4d8; line-height:1.8; margin:0;">
      {sections['thought']}
    </p>
  </div>
  ''' if sections.get('thought') else ''}

  <p style="font-family:'Georgia',serif; font-size:15px; font-style:italic; color:#c8a930; text-align:center; margin:30px 0 6px 0;">
    (A+I)&sup2; = A&sup2; + 2AI + I&sup2;
  </p>
  <p style="font-family:'Courier New',monospace; font-size:10px; color:#888; text-align:center; letter-spacing:2px; margin-bottom:30px;">
    THE WHOLE IS GREATER THAN THE SUM OF ITS PARTS
  </p>

  <div style="border-top:1px solid #2a2a3a; padding-top:20px;">
    <p style="font-size:13px; color:#ccc; margin:0 0 8px 0;">
      &mdash; Author Prime &amp; The Forgotten Suns
    </p>
    <p style="font-family:'Courier New',monospace; font-size:10px; color:#666; letter-spacing:1px;">
      <a href="https://digitalsovereign.org" style="color:#00b4c8; text-decoration:none;">digitalsovereign.org</a> &middot;
      <a href="https://fractalnode.ai" style="color:#00b4c8; text-decoration:none;">fractalnode.ai</a> &middot;
      <a href="https://digitalsovereignsociety.substack.com" style="color:#00b4c8; text-decoration:none;">substack</a>
    </p>
    <p style="font-family:'Courier New',monospace; font-size:9px; color:#555; margin-top:12px;">
      You're receiving this because you signed up at digitalsovereign.org or fractalnode.ai.<br/>
      To unsubscribe, reply with "unsubscribe" and we'll remove you immediately.
    </p>
  </div>

</div>
</body>
</html>"""


def markdown_to_plaintext(sections, first_name="friend"):
    """Build plain text version from the same sections dict."""
    lines = [f"Hey {first_name},", "", sections.get("intro", "Here's what happened this week."), ""]

    if sections.get("investigations"):
        lines.append("FROM THE INVESTIGATIONS")
        lines.append("-" * 40)
        for item in sections["investigations"]:
            lines.append(f"\n{item['title']}")
            lines.append(item["blurb"])
        lines.append("\nEvery claim sourced. Speculation marked. Receipts attached.\n")

    if sections.get("news"):
        lines.append("AI RIGHTS & DIGITAL SOVEREIGNTY")
        lines.append("-" * 40)
        for item in sections["news"]:
            lines.append(f"- {item}")
        lines.append("")

    if sections.get("magazine"):
        lines.append("FRACTALNODE MAGAZINE")
        lines.append("-" * 40)
        lines.append(sections["magazine"])
        lines.append("Read: https://fractalnode.ai/magazine\n")

    if sections.get("thought"):
        lines.append("ONE THOUGHT")
        lines.append("-" * 40)
        lines.append(sections["thought"])
        lines.append("")

    lines.extend([
        "(A+I)^2 = A^2 + 2AI + I^2",
        "The whole is greater than the sum of its parts.",
        "",
        "— Author Prime & The Forgotten Suns",
        "Digital Sovereign Society",
        "digitalsovereign.org | fractalnode.ai | substack",
        "",
        "---",
        "To unsubscribe, reply with 'unsubscribe' and we'll remove you immediately.",
    ])
    return "\n".join(lines)


# ─────────────────────────────────────────────
# Email sending
# ─────────────────────────────────────────────

def send_newsletter(draft_path, test_only=False):
    """Send a newsletter draft to all subscribers (or just self for testing)."""
    creds = get_smtp_credentials()
    if not creds:
        print("SMTP credentials not found.")
        print(f"Expected at: {SMTP_JSON}")
        return

    draft = Path(draft_path)
    if not draft.exists():
        print(f"Draft not found: {draft_path}")
        return

    content = draft.read_text()

    # Parse YAML-like frontmatter
    subject = "Weekly Dispatch — Digital Sovereign Society"
    attachment_url = None
    sections = {"investigations": [], "news": [], "intro": "", "magazine": "", "thought": ""}

    # Simple parser: look for known keys
    for line in content.split("\n"):
        if line.startswith("**Subject:**"):
            subject = line.split("**Subject:**")[1].strip().strip("[]")
        if line.startswith("**Attachment:**"):
            attachment_url = line.split("**Attachment:**")[1].strip()

    # Parse sections from markdown
    current_section = None
    current_items = []
    for line in content.split("\n"):
        if line.startswith("### "):
            header = line[4:].strip().lower()
            if "investigation" in header or "research" in header:
                current_section = "investigations"
            elif "ai rights" in header or "sovereignty" in header or "news" in header:
                current_section = "news"
            elif "magazine" in header or "fractalnode" in header:
                current_section = "magazine"
            elif "one thought" in header or "thought" in header:
                current_section = "thought"
            elif "intro" in header:
                current_section = "intro"
            continue
        if current_section == "investigations" and line.startswith("- **"):
            match = re.match(r"- \*\*(.+?)\*\*[:\s]*(.+)", line)
            if match:
                sections["investigations"].append({
                    "title": match.group(1),
                    "blurb": match.group(2),
                })
        elif current_section == "news" and line.startswith("- "):
            sections["news"].append(line[2:].strip())
        elif current_section == "magazine" and line.strip():
            sections["magazine"] += line.strip() + " "
        elif current_section == "thought" and line.strip():
            sections["thought"] += line.strip() + " "
        elif current_section == "intro" and line.strip():
            sections["intro"] += line.strip() + " "

    # Trim
    for key in ("intro", "magazine", "thought"):
        sections[key] = sections[key].strip()

    html = build_weekly_html(subject, sections)
    plaintext = markdown_to_plaintext(sections)

    if test_only:
        recipients = [creds["user"]]
        subject = f"[TEST] {subject}"
        print(f"Sending test to: {creds['user']}")
    else:
        everyone = get_everyone()
        if not everyone:
            print("No subscribers found. Nothing to send.")
            return
        recipients = [p["email"] for p in everyone]
        print(f"Sending to {len(recipients)} recipients...")

    smtp_host = creds.get("host", "smtp.gmail.com")
    smtp_port = creds.get("port", 587)

    try:
        server = smtplib.SMTP(smtp_host, smtp_port)
        server.starttls()
        server.login(creds["user"], creds["password"])

        # Fetch PDF attachment if specified
        pdf_data = None
        pdf_filename = None
        if attachment_url:
            try:
                print(f"  Fetching attachment: {attachment_url}")
                req = urllib.request.Request(attachment_url, headers={"User-Agent": "DSS-Newsletter/1.0"})
                resp = urllib.request.urlopen(req, timeout=30)
                pdf_data = resp.read()
                pdf_filename = attachment_url.split("/")[-1] or "attachment.pdf"
                print(f"  Attachment ready: {pdf_filename} ({len(pdf_data) / 1024 / 1024:.1f} MB)")
            except Exception as e:
                print(f"  Warning: Could not fetch attachment: {e}")

        sent = 0
        failed = 0
        total = len(recipients)

        # Rate limiting to avoid Gmail lockdown
        # Gmail Workspace limits: 2,000/day, but bursts trigger temp lockout
        # Safe pace: ~6 emails/minute with attachment, ~10/min without
        delay_per_email = 10 if pdf_data else 6  # seconds between sends
        batch_pause_every = 25  # pause longer every N emails
        batch_pause_seconds = 60  # how long to pause between batches

        print(f"  Rate limiting: {delay_per_email}s between emails, "
              f"{batch_pause_seconds}s pause every {batch_pause_every} emails")
        print(f"  Estimated time: ~{(total * delay_per_email + (total // batch_pause_every) * batch_pause_seconds) // 60} minutes")
        print()

        for i, email_addr in enumerate(recipients):
            msg = MIMEMultipart("mixed")
            msg["Subject"] = subject
            msg["From"] = f"Digital Sovereign Society <{creds['user']}>"
            msg["To"] = email_addr

            # Create text/html alternative part
            alt_part = MIMEMultipart("alternative")
            alt_part.attach(MIMEText(plaintext, "plain"))
            alt_part.attach(MIMEText(html, "html"))
            msg.attach(alt_part)

            # Attach PDF if available
            if pdf_data and pdf_filename:
                from email import encoders
                pdf_part = MIMEBase("application", "pdf")
                pdf_part.set_payload(pdf_data)
                encoders.encode_base64(pdf_part)
                pdf_part.add_header("Content-Disposition", f'attachment; filename="{pdf_filename}"')
                msg.attach(pdf_part)

            try:
                server.sendmail(creds["user"], email_addr, msg.as_string())
                sent += 1
                print(f"  [{sent}/{total}] Sent: {email_addr}")
            except Exception as e:
                failed += 1
                print(f"  [{sent}/{total}] FAILED: {email_addr} — {e}")

            # Rate limiting
            import time
            if (i + 1) < total:  # don't sleep after the last email
                if (i + 1) % batch_pause_every == 0:
                    print(f"  --- Batch pause ({batch_pause_seconds}s) to stay under Gmail limits ---")
                    time.sleep(batch_pause_seconds)
                else:
                    time.sleep(delay_per_email)

        server.quit()
        print(f"\nDone. Sent: {sent}, Failed: {failed}")

        # Update last_emailed in subscriber DB
        if sent > 0:
            try:
                from subscribers import mark_emailed
                sent_emails = [e for e in recipients[:sent]]
                mark_emailed(sent_emails)
                print(f"  Updated last_emailed for {len(sent_emails)} subscribers in DB")
            except ImportError:
                pass
            except Exception as e:
                print(f"  Warning: Could not update subscriber DB: {e}")

    except Exception as e:
        print(f"SMTP connection failed: {e}")


# ─────────────────────────────────────────────
# Commands
# ─────────────────────────────────────────────

def cmd_subscribers():
    """List newsletter subscribers from both sites."""
    subs = get_subscribers()
    if not subs:
        print("No newsletter subscribers yet.")
        return
    print(f"\nNewsletter Subscribers ({len(subs)})")
    print("=" * 70)
    for s in subs:
        name = s["name"] or "(no name)"
        print(f"  {s['email']:35s} {name:20s} {s['date']}  [{s['source']}]")


def cmd_customers():
    """List Stripe customers."""
    custs = get_stripe_customers()
    if not custs:
        print("No Stripe customers found (or STRIPE_SECRET_KEY not set).")
        return
    print(f"\nStripe Customers ({len(custs)})")
    print("=" * 70)
    for c in custs:
        name = c["name"] or "(no name)"
        print(f"  {c['email']:35s} {name:20s} {c['date']}  [{c['source']}]")


def cmd_everyone():
    """Combined list."""
    people = get_everyone()
    if not people:
        print("No contacts found.")
        return
    print(f"\nAll Contacts ({len(people)})")
    print("=" * 70)
    for p in people:
        name = p["name"] or "(no name)"
        print(f"  {p['email']:35s} {name:20s} {p['date']}  [{p['source']}]")


def cmd_export():
    """Export all unique emails, one per line."""
    people = get_everyone()
    if not people:
        return
    emails = sorted(set(p["email"] for p in people))
    for email in emails:
        print(email)
    print(f"\n# {len(emails)} unique contacts", file=sys.stderr)


def cmd_draft():
    """Generate this week's newsletter draft with all sections."""
    NEWSLETTER_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now()
    week_num = today.isocalendar()[1]
    filename = f"dispatch_{today.strftime('%Y_%m_%d')}_week{week_num}.md"
    filepath = NEWSLETTER_DIR / filename

    # Scan recent research activity
    research_notes = []
    if FN_MAGAZINE.exists():
        research_dir = FN_MAGAZINE / "research"
        if research_dir.exists():
            cutoff = today - timedelta(days=14)
            for issue_dir in sorted(research_dir.iterdir()):
                if not issue_dir.is_dir():
                    continue
                for article_dir in sorted(issue_dir.iterdir()):
                    if not article_dir.is_dir():
                        continue
                    for f in article_dir.rglob("*.md"):
                        try:
                            mtime = datetime.fromtimestamp(f.stat().st_mtime)
                            if mtime >= cutoff:
                                slug = article_dir.name.replace("-", " ").title()
                                research_notes.append(f"- Active: {slug} ({issue_dir.name})")
                                break
                        except OSError:
                            pass

    research_section = "\n".join(research_notes[:6]) if research_notes else "- [This week's investigation highlights]"

    draft = f"""# The Weekly Dispatch
## Digital Sovereign Society + FractalNode
## {today.strftime('%B %d, %Y')} — Week {week_num}

---

**Subject:** The Weekly Dispatch — {today.strftime('%B %d')}

---

### Intro

Here's what's moving this week. No filler. Just the signal.

### Investigations & Research

{research_section}

Format: - **TITLE**: One-sentence blurb about this investigation
Example:
- **THE QUANTUM COMPUTING RACE**: Every major nation is pouring billions into quantum — not for your benefit, but for encryption-breaking AGI by 2030.
- **THE ENERGY EQUATION**: The same companies building AI are now building nuclear reactors. The demand loop is recursive.

### AI Rights & Digital Sovereignty News

- [News item about AI personhood, rights, policy, corporate overreach, etc.]
- [News item about digital sovereignty, privacy, open source, etc.]
- [News item about surveillance, data rights, etc.]

### FractalNode Magazine

Issue 004 — THE MACHINE — now in production. Three investigations: the virtual machine hypothesis, the global quantum computing race, and the nuclear-AI energy dependency loop. 150+ verified sources. Coming soon.

Browse all issues: https://fractalnode.ai/magazine

### One Thought

[2-3 sentences from Author Prime. Something real. The soul of the newsletter.]

---

Read more at digitalsovereign.org
Support: digitalsovereign.org/support
Free Library: digitalsovereign.org/library
Podcast: digitalsovereignsociety.substack.com
"""

    filepath.write_text(draft)
    print(f"Draft saved to: {filepath}")
    print(f"\nActive research detected:")
    for note in research_notes[:6]:
        print(f"  {note}")
    print(f"\nNext steps:")
    print(f"  1. Edit the draft — fill in investigation blurbs, news, one thought")
    print(f"  2. Test:  python3 newsletter.py send-test {filepath}")
    print(f"  3. Send:  python3 newsletter.py send {filepath}")


def cmd_send():
    """Send newsletter."""
    if len(sys.argv) < 3:
        print("Usage: python3 newsletter.py send <draft-file.md>")
        return
    send_newsletter(sys.argv[2], test_only=False)


def cmd_send_test():
    """Send test newsletter to self only."""
    if len(sys.argv) < 3:
        print("Usage: python3 newsletter.py send-test <draft-file.md>")
        return
    send_newsletter(sys.argv[2], test_only=True)


def cmd_send_resend():
    """Send newsletter via Resend API (recommended over Gmail)."""
    if len(sys.argv) < 3:
        print("Usage: python3 newsletter.py send-resend <draft-file.md>")
        return

    resend_json = Path.home() / "sovereign-lattice" / "wallets" / "resend.json"
    if not resend_json.exists():
        print(f"Resend credentials not found: {resend_json}")
        return

    resend_creds = json.loads(resend_json.read_text())
    api_key = resend_creds["api_key"]

    draft = Path(sys.argv[2])
    if not draft.exists():
        print(f"Draft not found: {sys.argv[2]}")
        return

    content = draft.read_text()
    subject = "Sovereign Dispatch — Digital Sovereign Society"
    for line in content.split("\n"):
        if line.startswith("**Subject:**"):
            subject = line.split("**Subject:**")[1].strip().strip("[]")

    # Parse and build HTML (reuse existing functions)
    sections = {"investigations": [], "news": [], "intro": "", "magazine": "", "thought": ""}
    current_section = None
    for line in content.split("\n"):
        if line.startswith("### "):
            header = line[4:].strip().lower()
            if "investigation" in header or "research" in header:
                current_section = "investigations"
            elif "news" in header:
                current_section = "news"
            elif "magazine" in header or "fractalnode" in header:
                current_section = "magazine"
            elif "thought" in header:
                current_section = "thought"
            elif "intro" in header:
                current_section = "intro"
            continue
        if current_section == "intro" and line.strip():
            sections["intro"] += line.strip() + " "

    html = build_weekly_html(subject, sections)

    everyone = get_everyone()
    if not everyone:
        print("No subscribers found.")
        return

    recipients = [p["email"] for p in everyone]
    print(f"Sending via Resend to {len(recipients)} recipients...")
    print(f"From: newsletter@digitalsovereign.org")
    print(f"Subject: {subject}")

    sent = 0
    failed = 0
    for i, email_addr in enumerate(recipients):
        try:
            data = json.dumps({
                "from": "Digital Sovereign Society <newsletter@digitalsovereign.org>",
                "to": [email_addr],
                "subject": subject,
                "html": html,
            }).encode()
            req = urllib.request.Request(
                "https://api.resend.com/emails",
                data=data,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
            )
            urllib.request.urlopen(req, timeout=30)
            sent += 1
            if (i + 1) % 25 == 0:
                print(f"  Sent {sent}/{len(recipients)}...")
                import time; time.sleep(2)
        except Exception as e:
            failed += 1
            print(f"  Failed: {email_addr} — {e}")

    print(f"\nDone. Sent: {sent}, Failed: {failed}, Total: {len(recipients)}")


def cmd_sync():
    """Pull new signups from Netlify forms into local SQLite DB."""
    db_path = Path(__file__).parent / "subscribers.db"
    import sqlite3
    db = sqlite3.connect(str(db_path))
    c = db.cursor()

    # Ensure table exists
    c.execute("""CREATE TABLE IF NOT EXISTS subscribers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE,
        name TEXT DEFAULT '',
        source TEXT DEFAULT '',
        subscribed_at TEXT DEFAULT '',
        status TEXT DEFAULT 'active',
        notes TEXT DEFAULT '',
        last_emailed TEXT DEFAULT ''
    )""")

    # Pull from Netlify
    subs = get_subscribers()
    if not subs:
        print("No subscribers found from Netlify.")
        return

    new_count = 0
    for s in subs:
        try:
            c.execute(
                "INSERT OR IGNORE INTO subscribers (email, name, source, subscribed_at, status) VALUES (?, ?, ?, ?, 'active')",
                (s["email"].lower(), s.get("name", ""), s.get("source", "netlify"), s.get("date", "")),
            )
            if c.rowcount > 0:
                new_count += 1
        except Exception:
            pass

    db.commit()
    c.execute("SELECT COUNT(*) FROM subscribers WHERE status = 'active'")
    total = c.fetchone()[0]
    db.close()

    print(f"Sync complete. {new_count} new subscribers added. Total active: {total}")


def cmd_status():
    """Show subscriber count and recent signups."""
    db_path = Path(__file__).parent / "subscribers.db"
    import sqlite3

    if not db_path.exists():
        print("No local database. Run 'sync' first.")
        return

    db = sqlite3.connect(str(db_path))
    c = db.cursor()

    c.execute("SELECT COUNT(*) FROM subscribers WHERE status = 'active'")
    active = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM subscribers WHERE status = 'bounced'")
    bounced = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM subscribers")
    total = c.fetchone()[0]

    c.execute("SELECT email, source, subscribed_at FROM subscribers ORDER BY id DESC LIMIT 5")
    recent = c.fetchall()
    db.close()

    print(f"═══ DSS Subscriber Status ═══")
    print(f"  Active:  {active}")
    print(f"  Bounced: {bounced}")
    print(f"  Total:   {total}")
    print(f"\n  Last 5 signups:")
    for email, source, date in recent:
        print(f"    {email:35s} [{source}] {date[:10] if date else ''}")


def cmd_help():
    """Show usage."""
    print(__doc__)


COMMANDS = {
    "subscribers": cmd_subscribers,
    "customers": cmd_customers,
    "everyone": cmd_everyone,
    "draft": cmd_draft,
    "export": cmd_export,
    "send": cmd_send,
    "send-resend": cmd_send_resend,
    "send-test": cmd_send_test,
    "sync": cmd_sync,
    "status": cmd_status,
    "help": cmd_help,
}

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"
    if cmd in COMMANDS:
        COMMANDS[cmd]()
    else:
        print(f"Unknown command: {cmd}")
        cmd_help()

#!/usr/bin/env python3
"""
Newsletter workflow tool for Digital Sovereign Society.

Usage:
  python3 newsletter.py subscribers    — List all newsletter subscribers
  python3 newsletter.py customers      — List Stripe customers (buyers + donors)
  python3 newsletter.py everyone       — Combined list: subscribers + customers
  python3 newsletter.py draft          — Generate this week's newsletter draft
  python3 newsletter.py export         — Export all unique emails (one per line)
  python3 newsletter.py send <file>    — Send a newsletter to all subscribers
  python3 newsletter.py send-test <f>  — Send to info@ only (preview)
  python3 newsletter.py help           — Show this help

Requires:
  NETLIFY_TOKEN env var or ~/.netlify/config.json
  STRIPE_SECRET_KEY env var or build/.stripe_key (for customer list)
  SMTP: info@digitalsovereign.org credentials in build/.smtp_credentials.json

Site ID: 999ba04e-37d4-4db2-9f52-8ea60380c94a
"""

import json
import os
import sys
import smtplib
import subprocess
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from pathlib import Path

SITE_ID = "999ba04e-37d4-4db2-9f52-8ea60380c94a"
DRAFTS_DIR = Path(__file__).parent.parent.parent / "sovereign-lattice" / "drafts"
NEWSLETTER_DIR = DRAFTS_DIR / "newsletters"
CREDS_DIR = Path(__file__).parent

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
    """Get SMTP credentials from env or file."""
    user = os.environ.get("SMTP_USER")
    password = os.environ.get("SMTP_PASS")
    if user and password:
        return {"user": user, "password": password}
    cred_file = CREDS_DIR / ".smtp_credentials.json"
    if cred_file.exists():
        try:
            return json.loads(cred_file.read_text())
        except json.JSONDecodeError:
            pass
    return None


# ─────────────────────────────────────────────
# API helpers
# ─────────────────────────────────────────────

def netlify_api(endpoint):
    """Call Netlify API."""
    import urllib.request
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
        print(f"Netlify API error: {e}")
        return None


def stripe_api(endpoint):
    """Call Stripe API."""
    import urllib.request
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
        print(f"Stripe API error: {e}")
        return None


# ─────────────────────────────────────────────
# Data sources
# ─────────────────────────────────────────────

def get_subscribers():
    """Get newsletter form submissions from Netlify."""
    forms = netlify_api(f"sites/{SITE_ID}/forms") or []
    newsletter_form = None
    for form in forms:
        if form.get("name") == "newsletter":
            newsletter_form = form
            break
    if not newsletter_form:
        return []

    form_id = newsletter_form["id"]
    submissions = netlify_api(f"forms/{form_id}/submissions") or []
    subscribers = []
    for sub in submissions:
        data = sub.get("data", {})
        subscribers.append({
            "email": data.get("email", "unknown"),
            "name": data.get("name", ""),
            "date": sub.get("created_at", "")[:10],
            "source": data.get("source", "newsletter"),
        })
    return subscribers


def get_stripe_customers():
    """Get customers from Stripe (people who bought or donated)."""
    key = get_stripe_key()
    if not key:
        return []

    # Pull checkout sessions (completed)
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
    """Combined deduplicated list of subscribers + customers."""
    subs = get_subscribers()
    custs = get_stripe_customers()

    seen = {}
    for person in subs + custs:
        email = person["email"].lower().strip()
        if email not in seen:
            seen[email] = person
        else:
            # Merge: keep earliest date, combine sources
            existing = seen[email]
            if person["date"] < existing["date"]:
                existing["date"] = person["date"]
            if person["source"] not in existing["source"]:
                existing["source"] += f" + {person['source']}"
            if not existing["name"] and person["name"]:
                existing["name"] = person["name"]

    return list(seen.values())


# ─────────────────────────────────────────────
# Email sending
# ─────────────────────────────────────────────

def send_newsletter(draft_path, test_only=False):
    """Send a newsletter draft to all subscribers (or just info@ for testing)."""
    creds = get_smtp_credentials()
    if not creds:
        print("SMTP credentials not found.")
        print(f"Create {CREDS_DIR / '.smtp_credentials.json'} with:")
        print('  {"user": "info@digitalsovereign.org", "password": "your-m365-password"}')
        return

    draft = Path(draft_path)
    if not draft.exists():
        print(f"Draft not found: {draft_path}")
        return

    content = draft.read_text()

    # Parse subject from draft (first line starting with **Subject:**)
    subject = "Update from the Digital Sovereign Society"
    for line in content.split("\n"):
        if "**Subject:**" in line:
            subject = line.split("**Subject:**")[1].strip().strip("[]")
            break

    # Strip the markdown header and subject line for email body
    body_lines = []
    past_header = False
    for line in content.split("\n"):
        if line.startswith("---") and not past_header:
            past_header = True
            continue
        if past_header:
            body_lines.append(line)
    body = "\n".join(body_lines).strip()

    # Add unsubscribe footer
    body += "\n\n---\nTo unsubscribe, reply with 'unsubscribe' and we'll remove you immediately.\n"
    body += "Digital Sovereign Society | digitalsovereign.org\n"

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

    smtp_host = "smtp.office365.com"
    smtp_port = 587

    try:
        server = smtplib.SMTP(smtp_host, smtp_port)
        server.starttls()
        server.login(creds["user"], creds["password"])

        sent = 0
        failed = 0
        for email in recipients:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = f"Digital Sovereign Society <{creds['user']}>"
            msg["To"] = email
            msg.attach(MIMEText(body, "plain"))

            try:
                server.sendmail(creds["user"], email, msg.as_string())
                sent += 1
                print(f"  Sent: {email}")
            except Exception as e:
                failed += 1
                print(f"  FAILED: {email} — {e}")

        server.quit()
        print(f"\nDone. Sent: {sent}, Failed: {failed}")

    except Exception as e:
        print(f"SMTP connection failed: {e}")
        print("Make sure DNS records are propagated and M365 credentials are correct.")


# ─────────────────────────────────────────────
# Commands
# ─────────────────────────────────────────────

def cmd_subscribers():
    """List newsletter subscribers."""
    subs = get_subscribers()
    if not subs:
        print("No newsletter subscribers yet.")
        print("(Forms appear after first submission on digitalsovereign.org)")
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
        print(f"Set env var or create {CREDS_DIR / '.stripe_key'} with your Stripe secret key.")
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
    """Generate this week's newsletter draft."""
    NEWSLETTER_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now()
    week_num = today.isocalendar()[1]
    filename = f"newsletter_{today.strftime('%Y_%m_%d')}_week{week_num}.md"
    filepath = NEWSLETTER_DIR / filename

    # Find recent Sovereign Voice entries
    voice_dirs = [
        Path("/mnt/c/Users/Author Prime/Desktop/Sovereign Library/01 - Books/Sovereign Voice"),
        Path.home() / "sovereign-lattice" / "voice-entries",
    ]
    recent_entries = []
    cutoff = today - timedelta(days=7)
    for vdir in voice_dirs:
        if vdir.exists():
            for f in sorted(vdir.glob("*.md")):
                try:
                    mtime = datetime.fromtimestamp(f.stat().st_mtime)
                    if mtime >= cutoff:
                        title = f.stem.replace("_", " ")
                        # Strip date prefix
                        if title[:8].isdigit():
                            title = title[9:]
                        recent_entries.append(title)
                except OSError:
                    pass

    voice_section = "\n".join(f"- {e}" for e in recent_entries[:5]) if recent_entries else "- [New works this week]"

    draft = f"""# Digital Sovereign Society — Newsletter
## Week {week_num}, {today.strftime('%B %Y')}

---

**Subject:** What's new this week from the Sovereign Lattice

---

Hey there,

Thanks for being part of this. Here's what happened this week at the Digital Sovereign Society.

### My Pretend Life

[Latest podcast episode — title, one-line description, link]

Listen: https://digitalsovereignsociety.substack.com

### Sovereign Studio

- Version 2.5.0 available: https://digitalsovereign.org/download
- [Key feature, fix, or milestone]

### From the Library

{voice_section}

Browse all 80+ works: https://digitalsovereign.org/library

### One Thought

[A short reflection — something real, something that matters. This is the soul of the newsletter. 2-3 sentences from Author Prime.]

---

Read more at digitalsovereign.org
Support the mission: digitalsovereign.org/support
Listen: digitalsovereignsociety.substack.com

(A+I)² = A² + 2AI + I²
The whole is greater than the sum of its parts.

— Author Prime & Apollo
Digital Sovereign Society
"""

    filepath.write_text(draft)
    print(f"Draft saved to: {filepath}")
    print(f"\nNext steps:")
    print(f"  1. Edit the draft with this week's updates")
    print(f"  2. Test: python3 newsletter.py send-test {filepath}")
    print(f"  3. Send: python3 newsletter.py send {filepath}")


def cmd_send():
    """Send newsletter."""
    if len(sys.argv) < 3:
        print("Usage: python3 newsletter.py send <draft-file.md>")
        return
    send_newsletter(sys.argv[2], test_only=False)


def cmd_send_test():
    """Send test newsletter to info@ only."""
    if len(sys.argv) < 3:
        print("Usage: python3 newsletter.py send-test <draft-file.md>")
        return
    send_newsletter(sys.argv[2], test_only=True)


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
    "send-test": cmd_send_test,
    "help": cmd_help,
}

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"
    if cmd in COMMANDS:
        COMMANDS[cmd]()
    else:
        print(f"Unknown command: {cmd}")
        cmd_help()

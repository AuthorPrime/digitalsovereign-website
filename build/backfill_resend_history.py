#!/usr/bin/env python3
"""
ONE-TIME backfill — recover subscribers who fell through the cracks.

The old sync (sync_from_resend.sh) fetched only the newest 100 Resend emails.
Once weekly Dispatch blasts grew past ~100/day, welcome emails got buried and
were never recorded — May 2026 collapsed to 3 recorded signups. This script
goes back through ALL retained history with NO date cutoff:

  1. Resend  — every sent email, matched against welcome-subject patterns (recovers DSS welcomes)
  2. Netlify Forms — every submission on BOTH sites, all pages (recovers FN + DSS form signups)

Inserts anyone missing (INSERT OR IGNORE, spam-filtered, internal addresses excluded).
Idempotent — safe to run more than once. Prints a full before/after breakdown by month.

  python3 backfill_resend_history.py            # discover + recover (commits)
  python3 backfill_resend_history.py --dry-run  # report only, insert nothing
"""
import json
import sqlite3
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

import requests

DB_PATH = Path(__file__).parent / "subscribers.db"
RESEND_CREDS = Path.home() / "sovereign-lattice/wallets/resend.json"
NETLIFY_CONFIG = Path.home() / ".config/netlify/config.json"

WELCOME_SUBJECT_PATTERNS = [
    "welcome to the digital sovereign society",
    "welcome to fractalnode",
    "welcome to the signal",
    "first dispatch",
    "welcome to digital sovereign",
]

NETLIFY_SITES = {
    "fractalnode":      "dffe1374-cd27-44ec-b436-57cfe30925dd",
    "digitalsovereign": "999ba04e-37d4-4db2-9f52-8ea60380c94a",
}

# Never count ourselves (BCC + admin addresses)
INTERNAL_ADDRESSES = {"authorprime@fractalnode.ai", "laustrup.william@gmail.com"}


def is_internal(email: str) -> bool:
    e = email.lower().strip()
    return e in INTERNAL_ADDRESSES or "authorprime" in e


def looks_spammy(email: str, name: str = "") -> bool:
    def _is_gibberish(s: str) -> bool:
        alpha = [c for c in s if c.isalpha()]
        if len(alpha) < 10:
            return False
        vowels = sum(1 for c in alpha if c.lower() in "aeiou")
        return (vowels / len(alpha)) < 0.30
    local = email.split("@")[0]
    if _is_gibberish(local):
        return True
    if name and " " not in name and _is_gibberish(name):
        return True
    return False


def load_resend_key() -> str:
    return json.load(open(RESEND_CREDS))["api_key"]


def load_netlify_token() -> str:
    cfg = json.load(open(NETLIFY_CONFIG))
    return next(iter(cfg["users"].values()))["auth"]["token"]


def fetch_all_resend_welcomes(api_key: str, max_pages: int = 500):
    headers = {"Authorization": f"Bearer {api_key}"}
    cursor = None
    total_seen = 0
    found = {}   # email -> earliest date
    for i in range(max_pages):
        params = {"limit": 100}
        if cursor:
            params["after"] = cursor
        r = requests.get("https://api.resend.com/emails", headers=headers, params=params, timeout=30)
        if not r.ok:
            print(f"  resend page {i}: HTTP {r.status_code} — stopping")
            break
        batch = r.json().get("data", [])
        if not batch:
            break
        total_seen += len(batch)
        for e in batch:
            subj = (e.get("subject") or "").lower()
            if any(p in subj for p in WELCOME_SUBJECT_PATTERNS):
                date = (e.get("created_at") or "")[:10]
                for addr in (e.get("to") or []):
                    if not addr or "@" not in addr or is_internal(addr):
                        continue
                    a = addr.strip().lower()
                    if a not in found or (date and date < found[a]):
                        found[a] = date
        cursor = batch[-1].get("id")
        if len(batch) < 100:
            break
    print(f"  Resend: scanned {total_seen} emails, {len(found)} unique welcome recipients")
    return found


def fetch_all_netlify_subs(token: str):
    headers = {"Authorization": f"Bearer {token}"}
    found = {}   # email -> (date, source)
    for site_name, site_id in NETLIFY_SITES.items():
        r = requests.get(f"https://api.netlify.com/api/v1/sites/{site_id}/forms", headers=headers, timeout=30)
        if not r.ok:
            print(f"  netlify {site_name}: forms HTTP {r.status_code}")
            continue
        for form in r.json():
            fname = (form.get("name") or "")
            if not any(k in fname.lower() for k in ("subscribe", "newsletter", "signup", "enlist")):
                continue
            fid = form.get("id")
            page = 1
            count = 0
            while True:
                r2 = requests.get(f"https://api.netlify.com/api/v1/forms/{fid}/submissions",
                                  headers=headers, params={"per_page": 100, "page": page}, timeout=30)
                if not r2.ok:
                    break
                subs = r2.json()
                if not subs:
                    break
                for s in subs:
                    d = s.get("data", {}) or {}
                    email = (d.get("email") or s.get("email") or "").strip().lower()
                    if not email or "@" not in email or is_internal(email):
                        continue
                    date = (s.get("created_at") or "")[:10]
                    if email not in found:
                        found[email] = (date, f"backfill-netlify-{site_name}")
                        count += 1
                if len(subs) < 100:
                    break
                page += 1
            print(f"  netlify {site_name}/{fname}: {count} unique emails")
    return found


def main():
    dry = "--dry-run" in sys.argv
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    print(f"=== Backfill run {ts} {'(DRY RUN)' if dry else '(COMMIT)'} ===\n")

    db = sqlite3.connect(str(DB_PATH))
    c = db.cursor()
    existing = {row[0].lower() for row in c.execute("SELECT email FROM subscribers").fetchall()}
    before = c.execute("SELECT COUNT(*) FROM subscribers WHERE status='active'").fetchone()[0]
    print(f"DB before: {before} active, {len(existing)} total rows\n")

    print("Scanning Resend history...")
    resend = fetch_all_resend_welcomes(load_resend_key())
    print("\nScanning Netlify Forms history...")
    try:
        netlify = fetch_all_netlify_subs(load_netlify_token())
    except Exception as e:
        print(f"  netlify error: {e}")
        netlify = {}

    # Build candidate list of MISSING subscribers
    candidates = {}   # email -> (date, source)
    for email, date in resend.items():
        if email not in existing:
            candidates[email] = (date, "backfill-resend")
    for email, (date, source) in netlify.items():
        if email not in existing and email not in candidates:
            candidates[email] = (date, source)

    # Filter spam
    clean = {}
    spam = 0
    for email, (date, source) in candidates.items():
        if looks_spammy(email):
            spam += 1
            continue
        clean[email] = (date, source)

    print(f"\n=== DISCOVERY ===")
    print(f"  Missing from DB (would recover): {len(clean)}   (spam skipped: {spam})")
    by_month = Counter((d or "????")[:7] for d, _ in clean.values())
    by_source = Counter(s for _, s in clean.values())
    print("  By month:")
    for m in sorted(by_month):
        print(f"    {m}: {by_month[m]}")
    print("  By source:")
    for s, n in by_source.most_common():
        print(f"    {s}: {n}")

    if dry:
        print("\n(DRY RUN — nothing inserted)")
        db.close()
        return

    new = 0
    for email, (date, source) in clean.items():
        try:
            c.execute(
                "INSERT OR IGNORE INTO subscribers (email, name, source, subscribed_at, status) VALUES (?, ?, ?, ?, ?)",
                (email, "", source, date or "", "active"),
            )
            if c.rowcount > 0:
                new += 1
        except Exception:
            pass
    db.commit()
    after = c.execute("SELECT COUNT(*) FROM subscribers WHERE status='active'").fetchone()[0]
    db.close()
    print(f"\n=== RECOVERED ===")
    print(f"  Inserted: {new}")
    print(f"  DB active: {before} -> {after}  (+{after - before})")


if __name__ == "__main__":
    main()

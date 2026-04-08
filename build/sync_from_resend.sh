#!/bin/bash
# Sync subscribers from Resend welcome emails into local SQLite
# Runs via cron every 4 hours
# Uses curl (not urllib) to bypass Cloudflare

RESEND_KEY=$(python3 -c "import json; print(json.load(open('$HOME/sovereign-lattice/wallets/resend.json'))['api_key'])")
DB_DIR="$HOME/apollo-workspace/digitalsovereign-website/build"

curl -s "https://api.resend.com/emails?limit=100" \
  -H "Authorization: Bearer $RESEND_KEY" | python3 -c "
import sys, json, sqlite3
from pathlib import Path

data = json.load(sys.stdin)
emails = data.get('data', [])
DB_PATH = Path('$DB_DIR/subscribers.db')

new_subs = []
for e in emails:
    subj = e.get('subject', '')
    if 'first dispatch' in subj.lower():
        for addr in e.get('to', []):
            if addr and '@' in addr and 'authorprime' not in addr.lower():
                new_subs.append({
                    'email': addr.lower().strip(),
                    'date': e.get('created_at', '')[:10],
                })

db = sqlite3.connect(str(DB_PATH))
c = db.cursor()
new_count = 0
for s in new_subs:
    try:
        c.execute(
            'INSERT OR IGNORE INTO subscribers (email, name, source, subscribed_at, status) VALUES (?, ?, ?, ?, ?)',
            (s['email'], '', 'resend-welcome', s['date'], 'active')
        )
        if c.rowcount > 0:
            new_count += 1
    except: pass

db.commit()
c.execute('SELECT COUNT(*) FROM subscribers WHERE status = \"active\"')
total = c.fetchone()[0]
db.close()

from datetime import datetime
ts = datetime.now().strftime('%Y-%m-%d %H:%M')
print(f'[{ts}] Resend sync: {len(new_subs)} welcome emails found, {new_count} new, {total} total active')
"

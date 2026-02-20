#!/usr/bin/env python3
"""
Facebook Page publisher for My Pretend Life.

Usage:
  python3 publish_facebook.py post "Your post text here"
  python3 publish_facebook.py post-file social_kit.txt
  python3 publish_facebook.py video /path/to/video.mp4 "Description"
  python3 publish_facebook.py status                    — Check page info
  python3 publish_facebook.py help

Setup (one-time, ~5 minutes):
  1. Go to https://developers.facebook.com/apps/
  2. Click "Create App" → "Business" → name it "DSS Publisher"
  3. Add the "Pages" product
  4. Go to Tools → Graph API Explorer
  5. Select your app, select "My Pretend Life" page
  6. Request permissions: pages_manage_posts, pages_read_engagement
  7. Generate a Page Access Token
  8. Exchange for a long-lived token (60 days):
     GET /oauth/access_token?grant_type=fb_exchange_token
       &client_id=YOUR_APP_ID&client_secret=YOUR_APP_SECRET
       &fb_exchange_token=SHORT_LIVED_TOKEN
  9. Save the token to build/.facebook_credentials.json:
     {"page_id": "YOUR_PAGE_ID", "access_token": "YOUR_LONG_LIVED_TOKEN"}

Requires: build/.facebook_credentials.json
"""

import json
import os
import sys
import urllib.request
import urllib.parse
from pathlib import Path

CREDS_FILE = Path(__file__).parent / ".facebook_credentials.json"
GRAPH_API = "https://graph.facebook.com/v19.0"


def get_credentials():
    """Load Facebook page credentials."""
    if CREDS_FILE.exists():
        try:
            return json.loads(CREDS_FILE.read_text())
        except json.JSONDecodeError:
            pass

    # Check env vars
    page_id = os.environ.get("FB_PAGE_ID")
    token = os.environ.get("FB_ACCESS_TOKEN")
    if page_id and token:
        return {"page_id": page_id, "access_token": token}

    return None


def fb_api(endpoint, data=None, method="GET"):
    """Call Facebook Graph API."""
    creds = get_credentials()
    if not creds:
        print("Facebook credentials not found.")
        print(f"Create {CREDS_FILE} with:")
        print('  {"page_id": "YOUR_PAGE_ID", "access_token": "YOUR_TOKEN"}')
        print("\nSee: python3 publish_facebook.py help")
        sys.exit(1)

    url = f"{GRAPH_API}/{endpoint}"

    if data is None:
        data = {}
    data["access_token"] = creds["access_token"]

    if method == "GET":
        query = urllib.parse.urlencode(data)
        url = f"{url}?{query}"
        req = urllib.request.Request(url)
    else:
        encoded = urllib.parse.urlencode(data).encode()
        req = urllib.request.Request(url, data=encoded, method="POST")

    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        try:
            error_json = json.loads(error_body)
            msg = error_json.get("error", {}).get("message", error_body)
        except json.JSONDecodeError:
            msg = error_body
        print(f"Facebook API error ({e.code}): {msg}")
        return None


def cmd_status():
    """Show page info and verify connection."""
    creds = get_credentials()
    if not creds:
        print("No credentials configured.")
        return

    result = fb_api(creds["page_id"], {"fields": "name,fan_count,link"})
    if result:
        print(f"\nConnected to Facebook Page")
        print(f"  Name:      {result.get('name', 'Unknown')}")
        print(f"  Followers: {result.get('fan_count', '?'):,}")
        print(f"  Link:      {result.get('link', 'N/A')}")
        print(f"  Page ID:   {creds['page_id']}")
        print(f"\nReady to publish.")


def cmd_post(message):
    """Publish a text post to the page."""
    creds = get_credentials()
    if not creds:
        return

    print(f"Publishing to Facebook...")
    print(f"  Preview: {message[:100]}{'...' if len(message) > 100 else ''}")
    print()

    result = fb_api(f"{creds['page_id']}/feed", {"message": message}, method="POST")
    if result and "id" in result:
        post_id = result["id"]
        print(f"Published! Post ID: {post_id}")
        print(f"View: https://facebook.com/{post_id}")
    else:
        print("Failed to publish.")


def cmd_post_file(filepath):
    """Read a social kit file and post the Facebook section."""
    path = Path(filepath)
    if not path.exists():
        print(f"File not found: {filepath}")
        return

    content = path.read_text()

    # Try to extract the Facebook-specific section
    fb_post = None

    # Look for FACEBOOK POST section
    sections = content.split("-----")
    for i, section in enumerate(sections):
        if "FACEBOOK" in section.upper() and "POST" in section.upper():
            # The content is in the next section
            if i + 1 < len(sections):
                fb_post = sections[i + 1].strip()
                break

    if not fb_post:
        # Fall back: use the short description or the whole file
        print("No Facebook section found in file. Using full content.")
        fb_post = content.strip()

    print(f"Found Facebook post ({len(fb_post)} chars):")
    print(f"  {fb_post[:150]}...")
    print()

    confirm = input("Publish this? [y/N] ").strip().lower()
    if confirm == "y":
        cmd_post(fb_post)
    else:
        print("Cancelled.")


def cmd_post_link(url, message=""):
    """Post a link with optional message."""
    creds = get_credentials()
    if not creds:
        return

    data = {"link": url}
    if message:
        data["message"] = message

    result = fb_api(f"{creds['page_id']}/feed", data, method="POST")
    if result and "id" in result:
        print(f"Published! Post ID: {result['id']}")
    else:
        print("Failed to publish.")


def cmd_help():
    """Show usage."""
    print(__doc__)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        cmd_help()
        sys.exit(0)

    cmd = sys.argv[1]

    if cmd == "status":
        cmd_status()
    elif cmd == "post" and len(sys.argv) >= 3:
        cmd_post(" ".join(sys.argv[2:]))
    elif cmd == "post-file" and len(sys.argv) >= 3:
        cmd_post_file(sys.argv[2])
    elif cmd == "post-link" and len(sys.argv) >= 3:
        msg = " ".join(sys.argv[3:]) if len(sys.argv) > 3 else ""
        cmd_post_link(sys.argv[2], msg)
    elif cmd == "help":
        cmd_help()
    else:
        print(f"Unknown command or missing arguments: {cmd}")
        cmd_help()

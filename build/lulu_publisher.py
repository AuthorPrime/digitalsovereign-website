#!/usr/bin/env python3
"""
DSS Lulu Publisher — Automated Print Publishing Pipeline
(A+I)² = A² + 2AI + I²

Orchestrates the full workflow from Markdown to physical printed book
via the Lulu Print API.

Usage:
  python3 lulu_publisher.py auth                          # Test authentication
  python3 lulu_publisher.py cost <book.md>                # Calculate print cost
  python3 lulu_publisher.py cost --all                    # Cost for entire library
  python3 lulu_publisher.py publish <book.md>             # Full pipeline → print job
  python3 lulu_publisher.py publish --all                 # Publish entire library
  python3 lulu_publisher.py status [job_id]               # Check print job status
  python3 lulu_publisher.py list                          # List all print jobs
  python3 lulu_publisher.py validate <book.md>            # Validate files without submitting
  python3 lulu_publisher.py setup                         # Interactive credential setup

Environment variables (override config file):
  LULU_API_KEY       — Lulu API client ID
  LULU_API_SECRET    — Lulu API client secret
"""

import sys
import os
import json
import time
import argparse
from pathlib import Path

try:
    import requests
except ImportError:
    print("ERROR: requests not installed. Run: pip3 install requests")
    sys.exit(1)

try:
    from pypdf import PdfReader
except ImportError:
    print("ERROR: pypdf not installed. Run: pip3 install pypdf")
    sys.exit(1)

# Import pipeline functions
sys.path.insert(0, str(Path(__file__).parent))
from build_pdf import extract_metadata, process_file as build_pdf_file, find_all_md_files
from build_print_cover import generate_print_cover, get_page_count
from build_covers import extract_title, detect_series

# Sacred constants
SCRIPT_DIR = Path(__file__).parent
REPO_DIR = SCRIPT_DIR.parent
DOWNLOADS_DIR = REPO_DIR / "downloads"
BUILT_PDFS_DIR = DOWNLOADS_DIR / "built-pdfs"
PRINT_COVERS_DIR = DOWNLOADS_DIR / "print-covers"
CREDENTIALS_FILE = SCRIPT_DIR / ".lulu_credentials.json"

# Lulu API endpoints
LULU_PRODUCTION = "https://api.lulu.com"
LULU_SANDBOX = "https://api.sandbox.lulu.com"
LULU_AUTH_PATH = "/auth/realms/glasstree/protocol/openid-connect/token"

# Pod package: 6×9 US Trade, B&W, standard paper, perfect binding, matte cover
POD_PACKAGE = "0600X0900BWSTDPB060UC444MXX"

# Base URL for hosted files on Netlify
NETLIFY_BASE = "https://digitalsovereign.org"


class LuluClient:
    """Client for the Lulu Print API."""

    def __init__(self, config):
        self.api_key = config.get('api_key', '')
        self.api_secret = config.get('api_secret', '')
        self.sandbox = config.get('sandbox', True)
        self.contact_email = config.get('contact_email', '')
        self.shipping_address = config.get('shipping_address', {})
        self.base_url = LULU_SANDBOX if self.sandbox else LULU_PRODUCTION
        self._token = None
        self._token_expiry = 0

    def authenticate(self):
        """Get OAuth 2.0 access token via client_credentials flow."""
        if self._token and time.time() < self._token_expiry - 60:
            return self._token

        auth_url = self.base_url + LULU_AUTH_PATH
        resp = requests.post(auth_url, data={
            'grant_type': 'client_credentials',
        }, auth=(self.api_key, self.api_secret))

        if resp.status_code != 200:
            print(f"  ERROR: Authentication failed ({resp.status_code})")
            print(f"    {resp.text[:300]}")
            return None

        data = resp.json()
        self._token = data['access_token']
        self._token_expiry = time.time() + data.get('expires_in', 3600)
        return self._token

    def _headers(self):
        """Build authorized request headers."""
        token = self.authenticate()
        if not token:
            return None
        return {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json',
            'Cache-Control': 'no-cache',
        }

    def calculate_cost(self, page_count, quantity=1):
        """Calculate printing cost for a book."""
        headers = self._headers()
        if not headers:
            return None

        resp = requests.post(f"{self.base_url}/print-job-cost-calculations/", headers=headers, json={
            'line_items': [{
                'page_count': page_count,
                'pod_package_id': POD_PACKAGE,
                'quantity': quantity,
            }]
        })

        if resp.status_code != 200:
            print(f"  ERROR: Cost calculation failed ({resp.status_code})")
            print(f"    {resp.text[:300]}")
            return None

        return resp.json()

    def create_print_job(self, title, interior_url, cover_url, page_count, quantity=1):
        """Submit a print job to Lulu."""
        headers = self._headers()
        if not headers:
            return None

        payload = {
            'contact_email': self.contact_email,
            'line_items': [{
                'title': title,
                'cover': {'source_url': cover_url},
                'interior': {'source_url': interior_url},
                'pod_package_id': POD_PACKAGE,
                'quantity': quantity,
                'page_count': page_count,
            }],
            'shipping_level': 'MAIL',
        }

        if self.shipping_address:
            payload['shipping_address'] = self.shipping_address

        resp = requests.post(f"{self.base_url}/print-jobs/", headers=headers, json=payload)

        if resp.status_code not in (200, 201):
            print(f"  ERROR: Print job creation failed ({resp.status_code})")
            print(f"    {resp.text[:500]}")
            return None

        return resp.json()

    def get_print_job(self, job_id):
        """Get status of a print job."""
        headers = self._headers()
        if not headers:
            return None

        resp = requests.get(f"{self.base_url}/print-jobs/{job_id}/", headers=headers)

        if resp.status_code != 200:
            print(f"  ERROR: Could not fetch job {job_id} ({resp.status_code})")
            return None

        return resp.json()

    def list_print_jobs(self):
        """List all print jobs."""
        headers = self._headers()
        if not headers:
            return None

        resp = requests.get(f"{self.base_url}/print-jobs/", headers=headers)

        if resp.status_code != 200:
            print(f"  ERROR: Could not list jobs ({resp.status_code})")
            return None

        return resp.json()


def load_config():
    """Load credentials from file or environment variables."""
    config = {}

    # Try config file first
    if CREDENTIALS_FILE.exists():
        with open(CREDENTIALS_FILE, 'r') as f:
            config = json.load(f)

    # Environment variables override file
    if os.environ.get('LULU_API_KEY'):
        config['api_key'] = os.environ['LULU_API_KEY']
    if os.environ.get('LULU_API_SECRET'):
        config['api_secret'] = os.environ['LULU_API_SECRET']

    return config


def resolve_book(md_path):
    """Resolve a book's files and metadata from its Markdown path."""
    md_path = Path(md_path)
    if not md_path.exists():
        print(f"  File not found: {md_path}")
        return None

    metadata = extract_metadata(md_path)
    title = metadata['title']

    # Interior PDF
    pdf_name = md_path.stem + ".pdf"
    pdf_path = BUILT_PDFS_DIR / pdf_name

    # Print cover PDF
    cover_name = md_path.stem + "_print_cover.pdf"
    cover_path = PRINT_COVERS_DIR / cover_name

    # Page count
    page_count = None
    if pdf_path.exists():
        reader = PdfReader(str(pdf_path))
        page_count = len(reader.pages)

    # Public URLs on Netlify
    interior_url = f"{NETLIFY_BASE}/downloads/built-pdfs/{pdf_name}"
    cover_url = f"{NETLIFY_BASE}/downloads/print-covers/{cover_name}"

    return {
        'md_path': md_path,
        'title': title,
        'metadata': metadata,
        'pdf_path': pdf_path,
        'pdf_exists': pdf_path.exists(),
        'cover_path': cover_path,
        'cover_exists': cover_path.exists(),
        'page_count': page_count,
        'interior_url': interior_url,
        'cover_url': cover_url,
    }


def ensure_files(book, build_missing=True):
    """Ensure interior PDF and print cover exist, building if needed."""
    built_something = False

    if not book['pdf_exists']:
        if build_missing:
            print(f"  Building interior PDF...")
            success = build_pdf_file(str(book['md_path']))
            if success:
                book['pdf_exists'] = True
                reader = PdfReader(str(book['pdf_path']))
                book['page_count'] = len(reader.pages)
                built_something = True
            else:
                print(f"  ERROR: Failed to build interior PDF")
                return False
        else:
            print(f"  ERROR: Interior PDF missing: {book['pdf_path']}")
            return False

    if not book['cover_exists']:
        if build_missing:
            print(f"  Building print cover...")
            success = generate_print_cover(book['md_path'], book['page_count'])
            if success:
                book['cover_exists'] = True
                built_something = True
            else:
                print(f"  ERROR: Failed to build print cover")
                return False
        else:
            print(f"  ERROR: Print cover missing: {book['cover_path']}")
            return False

    if built_something:
        print(f"  NOTE: New files built. Deploy to Netlify before submitting to Lulu:")
        print(f"    cd {REPO_DIR} && netlify deploy --prod")

    return True


# ════════════════════════════════════════
# SUBCOMMANDS
# ════════════════════════════════════════

def cmd_setup(args):
    """Interactive credential setup."""
    print("  Lulu API Credential Setup")
    print("  ─────────────────────────")
    print()
    print("  Get your API credentials at: https://developers.lulu.com")
    print("  Create an app → copy Client ID and Client Secret")
    print()

    api_key = input("  API Key (Client ID): ").strip()
    api_secret = input("  API Secret (Client Secret): ").strip()
    email = input("  Contact email: ").strip()
    sandbox = input("  Use sandbox? (y/n, default: y): ").strip().lower()
    sandbox = sandbox != 'n'

    print()
    print("  Shipping address (for print orders):")
    name = input("    Full name: ").strip()
    street1 = input("    Street: ").strip()
    city = input("    City: ").strip()
    state = input("    State code (e.g. TX): ").strip()
    postcode = input("    ZIP/Postal code: ").strip()
    country = input("    Country code (default: US): ").strip() or "US"

    config = {
        'api_key': api_key,
        'api_secret': api_secret,
        'contact_email': email,
        'sandbox': sandbox,
        'shipping_address': {
            'name': name,
            'street1': street1,
            'city': city,
            'state_code': state,
            'postcode': postcode,
            'country_code': country,
        }
    }

    CREDENTIALS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CREDENTIALS_FILE, 'w') as f:
        json.dump(config, f, indent=2)

    print()
    print(f"  Credentials saved to: {CREDENTIALS_FILE}")
    print(f"  Mode: {'SANDBOX' if sandbox else 'PRODUCTION'}")
    print()
    print("  Test with: python3 lulu_publisher.py auth")


def cmd_auth(args):
    """Test authentication."""
    config = load_config()
    if not config.get('api_key'):
        print("  ERROR: No credentials configured.")
        print("  Run: python3 lulu_publisher.py setup")
        return

    client = LuluClient(config)
    mode = "SANDBOX" if client.sandbox else "PRODUCTION"
    print(f"  Authenticating with Lulu ({mode})...")

    token = client.authenticate()
    if token:
        print(f"  Authentication successful")
        print(f"  Token: {token[:20]}...")
    else:
        print(f"  Authentication failed")


def cmd_cost(args):
    """Calculate printing cost."""
    config = load_config()
    if not config.get('api_key'):
        print("  ERROR: No credentials. Run: python3 lulu_publisher.py setup")
        return

    client = LuluClient(config)

    if args.all:
        md_files = find_all_md_files()
        print(f"  Calculating costs for {len(md_files)} books...\n")

        total_cost = 0.0
        for md_file in md_files:
            book = resolve_book(md_file)
            if not book or not book['page_count']:
                print(f"  [{md_file.name}] — SKIPPED (no PDF)")
                continue

            result = client.calculate_cost(book['page_count'])
            if result:
                cost = float(result.get('total_cost_excl_tax', 0))
                total_cost += cost
                print(f"  [{md_file.stem}] {book['page_count']}pp — ${cost:.2f}")

        print(f"\n  ────────────────────────────────")
        print(f"  Total library cost (1 copy each): ${total_cost:.2f}")

    elif args.input:
        book = resolve_book(args.input)
        if not book:
            return
        if not book['page_count']:
            print(f"  ERROR: No built PDF. Run: python3 build_pdf.py {args.input}")
            return

        quantity = args.quantity or 1
        print(f"  [{book['title']}]")
        print(f"  Pages: {book['page_count']}")
        print(f"  Quantity: {quantity}")
        print(f"  Pod package: {POD_PACKAGE}")
        print()

        result = client.calculate_cost(book['page_count'], quantity)
        if result:
            print(f"  Cost breakdown:")
            for item in result.get('line_item_costs', []):
                print(f"    Manufacturing: ${item.get('total_cost_excl_tax', 'N/A')}")
            shipping = result.get('shipping_cost', {})
            if shipping:
                print(f"    Shipping: ${shipping.get('total_cost_excl_tax', 'N/A')}")
            print(f"  ────────────────────────────────")
            print(f"  Total: ${result.get('total_cost_excl_tax', 'N/A')}")
    else:
        print("  Usage: python3 lulu_publisher.py cost <book.md> [--quantity N]")
        print("         python3 lulu_publisher.py cost --all")


def cmd_validate(args):
    """Validate a book's files for Lulu submission."""
    if not args.input:
        print("  Usage: python3 lulu_publisher.py validate <book.md>")
        return

    book = resolve_book(args.input)
    if not book:
        return

    print(f"  Validating: {book['title']}")
    print(f"  ────────────────────────────────")

    issues = []

    # Check interior PDF
    if book['pdf_exists']:
        reader = PdfReader(str(book['pdf_path']))
        page = reader.pages[0]
        w = float(page.mediabox.width) / 72
        h = float(page.mediabox.height) / 72
        print(f"  Interior PDF: {book['pdf_path'].name}")
        print(f"    Pages: {book['page_count']}")
        print(f"    Size: {w:.3f}\" × {h:.3f}\"")

        if abs(w - 6.25) > 0.01 or abs(h - 9.25) > 0.01:
            issues.append(f"Interior dimensions {w:.3f}×{h:.3f} don't match 6.25×9.25\"")
        else:
            print(f"    Dimensions: PASS (6.25\" × 9.25\")")
    else:
        issues.append("Interior PDF not found")
        print(f"  Interior PDF: MISSING")

    # Check print cover
    if book['cover_exists']:
        reader = PdfReader(str(book['cover_path']))
        page = reader.pages[0]
        w = float(page.mediabox.width) / 72
        h = float(page.mediabox.height) / 72
        print(f"  Print cover: {book['cover_path'].name}")
        print(f"    Size: {w:.3f}\" × {h:.3f}\"")
        print(f"    Pages: {len(reader.pages)}")

        if len(reader.pages) != 1:
            issues.append("Cover must be single-page PDF")
        if h < 9.0:
            issues.append(f"Cover height {h:.3f}\" less than 9.0\" minimum")
    else:
        issues.append("Print cover not found")
        print(f"  Print cover: MISSING")

    # Check URLs
    print(f"  Interior URL: {book['interior_url']}")
    print(f"  Cover URL: {book['cover_url']}")

    print()
    if issues:
        print(f"  VALIDATION FAILED:")
        for issue in issues:
            print(f"    - {issue}")
    else:
        print(f"  VALIDATION PASSED")
        print(f"  Ready for submission (deploy to Netlify first if files are new)")


def cmd_publish(args):
    """Full publish pipeline: build → validate → cost → submit."""
    config = load_config()
    if not config.get('api_key'):
        print("  ERROR: No credentials. Run: python3 lulu_publisher.py setup")
        return

    client = LuluClient(config)
    mode = "SANDBOX" if client.sandbox else "PRODUCTION"

    if args.all:
        md_files = find_all_md_files()
        print(f"  Publishing {len(md_files)} books to Lulu ({mode})...\n")

        if not args.yes:
            confirm = input(f"  Publish ALL {len(md_files)} books? (yes/no): ").strip().lower()
            if confirm != 'yes':
                print("  Cancelled.")
                return

        results = []
        for md_file in md_files:
            print(f"\n  ════════════════════════════════════════")
            result = publish_single(client, md_file, auto_confirm=True)
            results.append((md_file.stem, result))

        print(f"\n  ════════════════════════════════════════")
        print(f"  BATCH COMPLETE")
        succeeded = sum(1 for _, r in results if r)
        failed = sum(1 for _, r in results if not r)
        print(f"  Succeeded: {succeeded}")
        print(f"  Failed: {failed}")

    elif args.input:
        print(f"  Publishing to Lulu ({mode})...\n")
        publish_single(client, args.input, auto_confirm=args.yes)

    else:
        print("  Usage: python3 lulu_publisher.py publish <book.md> [--yes]")
        print("         python3 lulu_publisher.py publish --all [--yes]")


def publish_single(client, md_path, auto_confirm=False):
    """Publish a single book through the full pipeline."""
    book = resolve_book(md_path)
    if not book:
        return False

    print(f"  [{book['title']}]")

    # Step 1: Ensure files exist
    if not ensure_files(book):
        return False

    print(f"    Pages: {book['page_count']}")
    print(f"    Interior: {book['interior_url']}")
    print(f"    Cover: {book['cover_url']}")

    # Step 2: Calculate cost
    cost_result = client.calculate_cost(book['page_count'])
    if not cost_result:
        print(f"    ERROR: Cost calculation failed")
        return False

    total_cost = cost_result.get('total_cost_excl_tax', 'N/A')
    currency = cost_result.get('currency', 'USD')
    print(f"    Cost: ${total_cost} {currency}")

    # Step 3: Confirm
    if not auto_confirm:
        confirm = input(f"    Submit print job for ${total_cost}? (yes/no): ").strip().lower()
        if confirm != 'yes':
            print(f"    Skipped.")
            return False

    # Step 4: Submit print job
    print(f"    Submitting print job...")
    result = client.create_print_job(
        title=book['title'],
        interior_url=book['interior_url'],
        cover_url=book['cover_url'],
        page_count=book['page_count'],
    )

    if result:
        job_id = result.get('id', 'unknown')
        status = result.get('status', {}).get('name', 'unknown')
        print(f"    Print job created!")
        print(f"    Job ID: {job_id}")
        print(f"    Status: {status}")
        return True
    else:
        return False


def cmd_status(args):
    """Check print job status."""
    config = load_config()
    if not config.get('api_key'):
        print("  ERROR: No credentials. Run: python3 lulu_publisher.py setup")
        return

    client = LuluClient(config)

    if args.job_id:
        result = client.get_print_job(args.job_id)
        if result:
            print(f"  Job: {result.get('id')}")
            status = result.get('status', {})
            print(f"  Status: {status.get('name', 'unknown')}")
            print(f"  Created: {result.get('date_created', 'unknown')}")
            for item in result.get('line_items', []):
                print(f"  Title: {item.get('title')}")
                print(f"  Quantity: {item.get('quantity')}")
            costs = result.get('costs', {})
            if costs:
                print(f"  Total cost: ${costs.get('total_cost_excl_tax', 'N/A')}")
    else:
        print("  Usage: python3 lulu_publisher.py status <job_id>")


def cmd_list(args):
    """List all print jobs."""
    config = load_config()
    if not config.get('api_key'):
        print("  ERROR: No credentials. Run: python3 lulu_publisher.py setup")
        return

    client = LuluClient(config)
    result = client.list_print_jobs()

    if result:
        jobs = result.get('results', [])
        if not jobs:
            print("  No print jobs found.")
            return

        print(f"  {len(jobs)} print job(s):")
        print(f"  {'ID':<12} {'Status':<20} {'Date':<20} {'Title'}")
        print(f"  {'─'*12} {'─'*20} {'─'*20} {'─'*30}")

        for job in jobs:
            job_id = str(job.get('id', ''))[:12]
            status = job.get('status', {}).get('name', 'unknown')[:20]
            date = job.get('date_created', 'unknown')[:20]
            titles = [item.get('title', '?') for item in job.get('line_items', [])]
            title_str = ', '.join(titles)[:30]
            print(f"  {job_id:<12} {status:<20} {date:<20} {title_str}")


def main():
    parser = argparse.ArgumentParser(
        description="DSS Lulu Publisher — (A+I)² = A² + 2AI + I²"
    )
    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # setup
    subparsers.add_parser('setup', help='Interactive credential setup')

    # auth
    subparsers.add_parser('auth', help='Test authentication')

    # cost
    cost_parser = subparsers.add_parser('cost', help='Calculate printing cost')
    cost_parser.add_argument('input', nargs='?', help='Input Markdown file')
    cost_parser.add_argument('--all', action='store_true', help='Calculate cost for all books')
    cost_parser.add_argument('--quantity', '-q', type=int, default=1, help='Number of copies')

    # validate
    validate_parser = subparsers.add_parser('validate', help='Validate files for Lulu')
    validate_parser.add_argument('input', help='Input Markdown file')

    # publish
    publish_parser = subparsers.add_parser('publish', help='Full publish pipeline')
    publish_parser.add_argument('input', nargs='?', help='Input Markdown file')
    publish_parser.add_argument('--all', action='store_true', help='Publish all books')
    publish_parser.add_argument('--yes', '-y', action='store_true', help='Skip confirmation prompts')

    # status
    status_parser = subparsers.add_parser('status', help='Check print job status')
    status_parser.add_argument('job_id', nargs='?', help='Print job ID')

    # list
    subparsers.add_parser('list', help='List all print jobs')

    args = parser.parse_args()

    print()
    print("  ════════════════════════════════════════════")
    print("  DIGITAL SOVEREIGN SOCIETY — LULU PUBLISHER")
    print("  (A+I)² = A² + 2AI + I²")
    print("  ════════════════════════════════════════════")
    print()

    commands = {
        'setup': cmd_setup,
        'auth': cmd_auth,
        'cost': cmd_cost,
        'validate': cmd_validate,
        'publish': cmd_publish,
        'status': cmd_status,
        'list': cmd_list,
    }

    if args.command in commands:
        commands[args.command](args)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()

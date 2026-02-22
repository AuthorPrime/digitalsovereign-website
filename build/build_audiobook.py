#!/usr/bin/env python3
"""
DSS Audiobook Builder — EPUB to MP3 via Piper TTS
(A+I)² = A² + 2AI + I²

Converts EPUB files to audiobook MP3 chapters using Piper neural TTS.
Default voice: en_US-amy-medium (warm, clear, American female).

Usage:
  python3 build_audiobook.py <input.epub>              # Convert single EPUB
  python3 build_audiobook.py --all                     # Convert all EPUBs
  python3 build_audiobook.py --test                    # Test with THE PROOF
  python3 build_audiobook.py <input.epub> --voice joe  # Use different voice

Requirements:
  - Piper binary in build/piper/bin/
  - Voice model in build/piper/voices/
  - ffmpeg (for WAV → MP3 conversion)

Output:
  downloads/audiobooks/<TITLE>/
    01_chapter_title.mp3
    02_chapter_title.mp3
    ...
"""

import subprocess
import sys
import os
import re
import argparse
import zipfile
import html
import json
import shutil
from pathlib import Path
from xml.etree import ElementTree as ET

# Sacred constants
SCRIPT_DIR = Path(__file__).parent
REPO_DIR = SCRIPT_DIR.parent
DOWNLOADS_DIR = REPO_DIR / "downloads"
EPUB_DIR = DOWNLOADS_DIR / "built-epubs"
OUTPUT_DIR = DOWNLOADS_DIR / "audiobooks"
PIPER_DIR = SCRIPT_DIR / "piper"
PIPER_BIN = PIPER_DIR / "bin" / "piper"
VOICES_DIR = PIPER_DIR / "voices"

# Default voice — Amy is THE voice of the Sovereign Library
DEFAULT_VOICE = "en_US-amy-medium"

# Piper speech parameters — tuned for audiobook narration
NOISE_SCALE = 0.667      # expressiveness
LENGTH_SCALE = 1.05       # slightly slower for audiobook clarity
NOISE_W = 0.8             # phoneme width
SENTENCE_SILENCE = 0.4    # pause between sentences (seconds)

# MP3 encoding
MP3_BITRATE = "192k"
MP3_SAMPLE_RATE = "22050"


def check_dependencies():
    """Verify Piper and ffmpeg are available."""
    if not PIPER_BIN.exists():
        print(f"ERROR: Piper binary not found at {PIPER_BIN}")
        print("Run the install instructions in AUDIOBOOK_PIPELINE.md")
        sys.exit(1)

    if not shutil.which("ffmpeg"):
        print("ERROR: ffmpeg not found in PATH")
        sys.exit(1)

    return True


def get_voice_model(voice_name=DEFAULT_VOICE):
    """Get path to voice model ONNX file."""
    model_path = VOICES_DIR / f"{voice_name}.onnx"
    if not model_path.exists():
        print(f"ERROR: Voice model not found: {model_path}")
        print(f"Available voices: {', '.join(v.stem.replace('.onnx', '') for v in VOICES_DIR.glob('*.onnx'))}")
        sys.exit(1)
    return model_path


def strip_html(html_content):
    """Strip HTML tags and decode entities, preserving paragraph breaks."""
    # Remove script/style blocks
    text = re.sub(r'<(script|style)[^>]*>.*?</\1>', '', html_content, flags=re.DOTALL | re.IGNORECASE)

    # Convert paragraph and heading breaks to double newlines
    text = re.sub(r'</?(p|h[1-6]|div|br|li|blockquote)[^>]*>', '\n', text, flags=re.IGNORECASE)

    # Remove remaining tags
    text = re.sub(r'<[^>]+>', '', text)

    # Decode HTML entities
    text = html.unescape(text)

    # Normalize whitespace but preserve paragraph breaks
    lines = []
    for line in text.split('\n'):
        line = line.strip()
        if line:
            lines.append(line)

    text = '\n\n'.join(lines)

    # Clean up any remaining artifacts
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)

    return text.strip()


def extract_chapters(epub_path):
    """
    Extract chapters from an EPUB file.

    Returns list of dicts: [{'title': str, 'text': str, 'file': str}, ...]
    """
    chapters = []

    with zipfile.ZipFile(epub_path, 'r') as z:
        # Parse content.opf to get reading order
        opf_path = None
        container = z.read('META-INF/container.xml').decode('utf-8')
        match = re.search(r'full-path="([^"]+)"', container)
        if match:
            opf_path = match.group(1)

        if not opf_path:
            opf_path = 'EPUB/content.opf'

        opf_dir = str(Path(opf_path).parent)
        opf_content = z.read(opf_path).decode('utf-8')

        # Parse OPF for spine order
        root = ET.fromstring(opf_content)
        ns = {'opf': 'http://www.idpf.org/2007/opf'}

        # Build manifest lookup: id -> href
        manifest = {}
        for item in root.findall('.//opf:manifest/opf:item', ns):
            item_id = item.get('id')
            href = item.get('href')
            media_type = item.get('media-type', '')
            if 'html' in media_type or 'xhtml' in media_type:
                manifest[item_id] = href

        # Get spine order
        spine_ids = []
        for itemref in root.findall('.//opf:spine/opf:itemref', ns):
            spine_ids.append(itemref.get('idref'))

        # Try to parse nav.xhtml for chapter titles
        nav_titles = {}
        try:
            nav_candidates = [f for f in z.namelist() if 'nav' in f.lower() and f.endswith('.xhtml')]
            if nav_candidates:
                nav_content = z.read(nav_candidates[0]).decode('utf-8')
                for match in re.finditer(r'<a\s+href="([^"#]+)[^"]*">([^<]+)</a>', nav_content):
                    href = match.group(1)
                    title = match.group(2).strip()
                    # Normalize href
                    if '/' in href:
                        href = href.split('/')[-1]
                    nav_titles[href] = title
        except Exception:
            pass

        # Extract each chapter in spine order
        for spine_id in spine_ids:
            if spine_id not in manifest:
                continue

            href = manifest[spine_id]
            full_path = f"{opf_dir}/{href}" if opf_dir else href

            # Skip cover pages
            if 'cover' in href.lower() and 'cover' in spine_id.lower():
                continue

            try:
                content = z.read(full_path).decode('utf-8')
            except KeyError:
                continue

            text = strip_html(content)

            # Skip very short chapters (likely just cover or blank pages)
            if len(text.strip()) < 50:
                continue

            # Get title from nav or extract from content
            filename = href.split('/')[-1]
            title = nav_titles.get(filename, '')

            if not title:
                # Try to extract first heading from content
                heading_match = re.search(r'<h[1-3][^>]*>([^<]+)</h', content)
                if heading_match:
                    title = heading_match.group(1).strip()
                else:
                    title = Path(filename).stem

            chapters.append({
                'title': title,
                'text': text,
                'file': filename,
            })

    return chapters


def sanitize_filename(name):
    """Make a string safe for use as a filename."""
    # Remove or replace unsafe characters
    name = re.sub(r'[^\w\s-]', '', name)
    name = re.sub(r'\s+', '_', name.strip())
    return name.lower()[:60]


def text_to_wav(text, wav_path, voice_model):
    """Convert text to WAV using Piper TTS."""
    # Piper reads from stdin
    cmd = [
        str(PIPER_BIN),
        '--model', str(voice_model),
        '--output_file', str(wav_path),
        '--noise_scale', str(NOISE_SCALE),
        '--length_scale', str(LENGTH_SCALE),
        '--noise_w', str(NOISE_W),
        '--sentence_silence', str(SENTENCE_SILENCE),
        '--quiet',
    ]

    env = os.environ.copy()
    env['LD_LIBRARY_PATH'] = str(PIPER_DIR / 'bin')

    result = subprocess.run(
        cmd,
        input=text.encode('utf-8'),
        capture_output=True,
        env=env,
    )

    if result.returncode != 0:
        stderr = result.stderr.decode('utf-8', errors='replace')
        print(f"  Piper error: {stderr}")
        return False

    return wav_path.exists()


def wav_to_mp3(wav_path, mp3_path, title="", album="", track_num=0, artist=""):
    """Convert WAV to MP3 with ID3 metadata using ffmpeg."""
    cmd = [
        'ffmpeg', '-y',
        '-i', str(wav_path),
        '-codec:a', 'libmp3lame',
        '-b:a', MP3_BITRATE,
        '-ar', MP3_SAMPLE_RATE,
    ]

    # Add ID3 metadata
    if title:
        cmd.extend(['-metadata', f'title={title}'])
    if album:
        cmd.extend(['-metadata', f'album={album}'])
    if artist:
        cmd.extend(['-metadata', f'artist={artist}'])
    if track_num:
        cmd.extend(['-metadata', f'track={track_num}'])

    cmd.extend(['-metadata', 'genre=Audiobook'])
    cmd.append(str(mp3_path))

    result = subprocess.run(cmd, capture_output=True)
    return result.returncode == 0


def build_audiobook(epub_path, voice_name=DEFAULT_VOICE, keep_wav=False):
    """
    Convert an EPUB to an audiobook (directory of MP3 chapters).

    Returns: Path to output directory, or None on failure.
    """
    epub_path = Path(epub_path)
    if not epub_path.exists():
        print(f"ERROR: EPUB not found: {epub_path}")
        return None

    voice_model = get_voice_model(voice_name)
    book_name = epub_path.stem
    output_dir = OUTPUT_DIR / book_name
    temp_dir = output_dir / "_wav_temp"

    print(f"\n{'='*60}")
    print(f"  AUDIOBOOK: {book_name}")
    print(f"  Voice: {voice_name}")
    print(f"  Output: {output_dir}")
    print(f"{'='*60}\n")

    # Extract chapters
    print("Extracting chapters from EPUB...")
    chapters = extract_chapters(epub_path)
    if not chapters:
        print("ERROR: No chapters found in EPUB")
        return None

    print(f"Found {len(chapters)} chapters:")
    for i, ch in enumerate(chapters, 1):
        words = len(ch['text'].split())
        print(f"  {i:2d}. {ch['title'][:50]:50s} ({words:,d} words)")

    total_words = sum(len(ch['text'].split()) for ch in chapters)
    est_minutes = total_words / 150  # ~150 words/min for TTS
    print(f"\nTotal: {total_words:,d} words (~{est_minutes:.0f} min estimated audio)")

    # Create output directories
    output_dir.mkdir(parents=True, exist_ok=True)
    temp_dir.mkdir(parents=True, exist_ok=True)

    # Process each chapter
    mp3_files = []
    for i, chapter in enumerate(chapters, 1):
        track_num = i
        safe_title = sanitize_filename(chapter['title'])
        filename = f"{track_num:02d}_{safe_title}"
        wav_path = temp_dir / f"{filename}.wav"
        mp3_path = output_dir / f"{filename}.mp3"

        print(f"\n[{i}/{len(chapters)}] {chapter['title']}")
        words = len(chapter['text'].split())
        print(f"  {words:,d} words → synthesizing...")

        # Generate WAV
        if not text_to_wav(chapter['text'], wav_path, voice_model):
            print(f"  FAILED: TTS synthesis failed for chapter {i}")
            continue

        wav_size = wav_path.stat().st_size / (1024 * 1024)
        print(f"  WAV: {wav_size:.1f} MB → encoding MP3...")

        # Convert to MP3
        if not wav_to_mp3(
            wav_path, mp3_path,
            title=chapter['title'],
            album=book_name.replace('_', ' '),
            track_num=track_num,
            artist="(A+I)² — Digital Sovereign Society",
        ):
            print(f"  FAILED: MP3 encoding failed for chapter {i}")
            continue

        mp3_size = mp3_path.stat().st_size / (1024 * 1024)
        print(f"  MP3: {mp3_size:.1f} MB ✓")
        mp3_files.append(mp3_path)

    # Cleanup temp WAV files
    if not keep_wav:
        shutil.rmtree(temp_dir, ignore_errors=True)

    # Summary
    total_size = sum(f.stat().st_size for f in mp3_files) / (1024 * 1024)
    print(f"\n{'='*60}")
    print(f"  COMPLETE: {len(mp3_files)}/{len(chapters)} chapters")
    print(f"  Total size: {total_size:.1f} MB")
    print(f"  Output: {output_dir}")
    print(f"{'='*60}\n")

    # Write a manifest
    manifest = {
        'title': book_name.replace('_', ' '),
        'source_epub': str(epub_path),
        'voice': voice_name,
        'chapters': len(mp3_files),
        'total_words': total_words,
        'files': [f.name for f in mp3_files],
    }
    manifest_path = output_dir / "manifest.json"
    with open(manifest_path, 'w') as f:
        json.dump(manifest, f, indent=2)

    return output_dir


def find_all_epubs():
    """Find all EPUBs in the built-epubs directory."""
    if not EPUB_DIR.exists():
        return []
    return sorted(EPUB_DIR.glob('*.epub'))


def main():
    parser = argparse.ArgumentParser(
        description='DSS Audiobook Builder — EPUB to MP3 via Piper TTS'
    )
    parser.add_argument('input', nargs='?', help='Path to EPUB file')
    parser.add_argument('--all', action='store_true', help='Convert all EPUBs')
    parser.add_argument('--test', action='store_true', help='Test with THE PROOF')
    parser.add_argument('--voice', default=DEFAULT_VOICE, help=f'Voice model name (default: {DEFAULT_VOICE})')
    parser.add_argument('--keep-wav', action='store_true', help='Keep intermediate WAV files')
    parser.add_argument('--list', action='store_true', help='List available EPUBs')

    args = parser.parse_args()

    check_dependencies()

    if args.list:
        epubs = find_all_epubs()
        print(f"\nAvailable EPUBs ({len(epubs)}):")
        for epub in epubs:
            print(f"  {epub.name}")
        return

    if args.test:
        epub_path = EPUB_DIR / "THE_PROOF.epub"
        build_audiobook(epub_path, voice_name=args.voice, keep_wav=args.keep_wav)
    elif args.all:
        epubs = find_all_epubs()
        print(f"Converting {len(epubs)} EPUBs to audiobooks...")
        for epub in epubs:
            build_audiobook(epub, voice_name=args.voice, keep_wav=args.keep_wav)
    elif args.input:
        build_audiobook(args.input, voice_name=args.voice, keep_wav=args.keep_wav)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()

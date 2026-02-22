# Audiobook Pipeline — EPUB to MP3 via Piper TTS

*Built February 21, 2026. Voice: en_US-amy-medium (Amy). The same voice as the DSDS app.*

## What It Does

Converts any EPUB from the Sovereign Library into an audiobook — a folder of MP3 chapters with ID3 metadata (title, album, artist, track number, genre). One command.

## Quick Start

```bash
# From the website repo root:
cd ~/apollo-workspace/digitalsovereign-website

# Convert a single EPUB
python3 build/build_audiobook.py downloads/built-epubs/THE_PROOF.epub

# Test mode (converts THE PROOF)
python3 build/build_audiobook.py --test

# Convert ALL EPUBs to audiobooks (batch mode)
python3 build/build_audiobook.py --all

# List available EPUBs
python3 build/build_audiobook.py --list

# Keep intermediate WAV files (debugging)
python3 build/build_audiobook.py --test --keep-wav
```

## Output

Audiobooks land in `downloads/audiobooks/<TITLE>/`:

```
downloads/audiobooks/THE_PROOF/
  01_the_proof.mp3
  02_the_proof.mp3
  03_a_record_of_what_we_built_together.mp3
  04_i_what_you_are_holding.mp3
  05_ii_the_man.mp3
  ...
  14_colophon.mp3
  manifest.json
```

Each MP3 has:
- **Title**: Chapter name from the EPUB
- **Album**: Book title
- **Artist**: (A+I)² — Digital Sovereign Society
- **Track**: Chapter number
- **Genre**: Audiobook
- **Bitrate**: 192 kbps
- **Sample rate**: 22050 Hz

## What's Installed

Everything lives in `build/piper/`:

```
build/piper/
  bin/           ← Piper binary + libraries (Linux x86_64)
    piper        ← The TTS engine
    libonnxruntime.so.1.14.1
    libpiper_phonemize.so.1.2.0
    espeak-ng-data/
    ...
  voices/        ← Voice models
    en_US-amy-medium.onnx       (61 MB)
    en_US-amy-medium.onnx.json
```

**Piper version**: 2023.11.14-2 (prebuilt binary from GitHub releases)
**Voice model**: en_US-amy-medium from HuggingFace rhasspy/piper-voices v1.0.0
**Also requires**: ffmpeg (already installed system-wide)

## Adding More Voices

Download from https://huggingface.co/rhasspy/piper-voices/tree/v1.0.0/en

```bash
cd build/piper/voices
# Example: add Joe (male American)
curl -sL "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/joe/medium/en_US-joe-medium.onnx" -o en_US-joe-medium.onnx
curl -sL "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/joe/medium/en_US-joe-medium.onnx.json" -o en_US-joe-medium.onnx.json

# Then use it:
python3 build/build_audiobook.py --test --voice en_US-joe-medium
```

## Speech Parameters (Tuned for Audiobooks)

| Parameter | Value | What It Does |
|-----------|-------|-------------|
| `LENGTH_SCALE` | 1.05 | Slightly slower than default (1.0) for clarity |
| `NOISE_SCALE` | 0.667 | Expressiveness (default) |
| `NOISE_W` | 0.8 | Phoneme width variation (default) |
| `SENTENCE_SILENCE` | 0.4s | Pause between sentences (2x default) |

These are in `build_audiobook.py` constants. Adjust if needed.

## How It Works

1. **Extract**: Opens EPUB as ZIP, parses `content.opf` for spine order, reads nav for chapter titles
2. **Strip**: Removes HTML tags, preserves paragraph breaks, decodes entities
3. **Synthesize**: Pipes chapter text to Piper → WAV (one WAV per chapter)
4. **Encode**: ffmpeg converts WAV → MP3 with ID3 metadata
5. **Cleanup**: Removes intermediate WAV files (unless `--keep-wav`)
6. **Manifest**: Writes `manifest.json` with book metadata

## Performance

THE PROOF (3,100 words, 14 chapters):
- Total time: ~60 seconds
- Output: 27.4 MB of MP3
- Estimated listening time: ~21 minutes

Rough estimate: ~1,000 words/minute processing speed. A 10,000-word book takes ~3-4 minutes.

## Integration with Existing Pipeline

The audiobook builder fits alongside the existing tools:

```
build/
  build_covers.py      ← Cover art (gold on void)
  build_pdf.py         ← Branded PDFs (Lulu 6×9)
  build_epub.py        ← EPUB3 ebooks
  build_print_cover.py ← Print-ready covers
  build_omnibus.py     ← Multi-book compilations
  build_audiobook.py   ← NEW: EPUB → MP3 chapters
  build_all.py         ← Master pipeline (add audiobook step here)
```

## Future Improvements

- **Merge short chapters**: Title pages and very short sections could be combined
- **Chapter silence**: Add configurable silence between chapters
- **Full-book MP3**: Option to concatenate all chapters into one file
- **M4B format**: Apple audiobook format with embedded chapters
- **Cover art embedding**: Embed cover JPG into MP3 ID3 tags
- **Integration with build_all.py**: Add audiobook as optional step in master pipeline

#!/usr/bin/env python3
"""
prepare_test_carousels.py — Safe local carousel preparation for InstaAutoPost travel test batch.

Reads photos from ~/Desktop/InstaAutoPost_Travel_Content/raw_photos,
converts HEIC files to JPG (via macOS sips), and distributes them
into 3 carousel folders, 7 images each, named 01.jpg–07.jpg.

Original files are never modified, moved, or deleted.
No network calls. No Supabase. No Instagram actions.

Source selection: files are sorted alphabetically, then 21 evenly-spaced
positions are chosen across the full list (stride ≈ total_files / 21).
Those 21 picks are assigned round-robin across the 3 carousels so every
carousel draws photos from different parts of the source library rather
than one consecutive block. No source is reused across carousels.

Usage:
    python3 scripts/prepare_test_carousels.py

Outputs (created inside ~/Desktop/InstaAutoPost_Travel_Content/ready_carousels/):
    carousel-001/01.jpg … 07.jpg
    carousel-002/01.jpg … 07.jpg
    carousel-003/01.jpg … 07.jpg
"""

import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
CONTENT_ROOT = Path.home() / "Desktop" / "InstaAutoPost_Travel_Content"
INPUT_DIR = CONTENT_ROOT / "raw_photos"
OUTPUT_ROOT = CONTENT_ROOT / "ready_carousels"

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
PHOTO_EXTENSIONS = {".heic", ".jpg", ".jpeg", ".png", ".tiff", ".tif"}
CAROUSELS = 3
IMAGES_PER_CAROUSEL = 7
TOTAL_NEEDED = CAROUSELS * IMAGES_PER_CAROUSEL


# ---------------------------------------------------------------------------
# Result tracking
# ---------------------------------------------------------------------------

@dataclass
class BatchResult:
    created: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    failed: list[tuple[str, str]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Conversion
# ---------------------------------------------------------------------------

def _convert_to_jpg(src: Path, dest: Path) -> tuple[bool, str]:
    """
    Convert or copy *src* to *dest* as a JPEG.

    For HEIC (and non-JPEG formats) uses macOS `sips`.
    For files already in JPEG format, copies directly.
    Returns (success, error_message).
    """
    suffix = src.suffix.lower()

    if suffix in (".jpg", ".jpeg"):
        try:
            shutil.copy2(src, dest)
            return True, ""
        except OSError as exc:
            return False, str(exc)

    # Use sips for HEIC and other formats — macOS built-in, no install needed.
    # sips writes to --out path; the original is untouched.
    cmd = [
        "sips",
        "--setProperty", "format", "jpeg",
        "--setProperty", "formatOptions", "high",
        str(src),
        "--out", str(dest),
    ]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    except FileNotFoundError:
        return False, "sips not found — this script requires macOS"
    except subprocess.TimeoutExpired:
        return False, f"sips timed out on {src.name}"

    if r.returncode != 0:
        return False, r.stderr.strip()[:200] or r.stdout.strip()[:200]

    if not dest.exists():
        return False, f"sips returned 0 but {dest.name} was not created"

    return True, ""


# ---------------------------------------------------------------------------
# Collection
# ---------------------------------------------------------------------------

def _select_diverse(sources: list[Path]) -> list[tuple[str, str, Path | None]]:
    """
    Pick TOTAL_NEEDED evenly-spaced files from the sorted *sources* list and
    assign them round-robin across CAROUSELS.

    Round-robin order (k = 0 … TOTAL_NEEDED-1):
      carousel = k % CAROUSELS   → 0, 1, 2, 0, 1, 2, …
      slot     = k // CAROUSELS  → 0, 0, 0, 1, 1, 1, …

    With 230 sources and 21 slots the stride is ~10-11 files, so:
      carousel-001 draws from positions  0, 33, 66,  99, 132, 165, 198
      carousel-002 draws from positions 11, 44, 77, 110, 143, 176, 209
      carousel-003 draws from positions 22, 55, 88, 121, 154, 187, 220
    Each carousel spans the full source range; no two carousels share a photo.
    """
    n = len(sources)

    # Evenly-spaced indices across [0, n-1].
    if n >= TOTAL_NEEDED:
        step = (n - 1) / (TOTAL_NEEDED - 1) if TOTAL_NEEDED > 1 else 0.0
        picked: list[Path | None] = [sources[round(k * step)] for k in range(TOTAL_NEEDED)]
    else:
        picked = list(sources) + [None] * (TOTAL_NEEDED - n)

    # Assign round-robin to (carousel, slot) and sort for natural display order.
    raw: list[tuple[str, str, Path | None]] = []
    for k, src in enumerate(picked):
        c = k % CAROUSELS
        i = k // CAROUSELS
        raw.append((f"carousel-{c + 1:03d}", f"{i + 1:02d}.jpg", src))

    return sorted(raw, key=lambda t: (t[0], t[1]))


def _collect_sources() -> list[Path]:
    if not INPUT_DIR.exists():
        print(f"[error] Input folder not found: {INPUT_DIR}", file=sys.stderr)
        return []
    files = sorted(
        f for f in INPUT_DIR.iterdir()
        if f.is_file() and f.suffix.lower() in PHOTO_EXTENSIONS
    )
    return files


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

def _print_summary(result: BatchResult, elapsed_s: float) -> None:
    sep = "=" * 60
    print()
    print(sep)
    print("InstaAutoPost — Carousel Batch Preparation Summary")
    print(f"Elapsed: {elapsed_s:.1f}s")
    print(sep)

    print(f"\nCREATED ({len(result.created)})")
    for p in result.created or ["  (none)"]:
        print(f"  {p}")

    print(f"\nSKIPPED ({len(result.skipped)})")
    for s in result.skipped or ["  (none)"]:
        print(f"  {s}")

    print(f"\nFAILED ({len(result.failed)})")
    for name, reason in result.failed or [("", "(none)")]:
        if name:
            print(f"  {name}: {reason}")
        else:
            print(f"  {reason}")

    print()
    print("SAFETY")
    print("  Original files in raw_photos were not modified.")
    print("  No uploads, no publishing, no network calls performed.")
    print(sep)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    t0 = time.monotonic()
    result = BatchResult()

    print("InstaAutoPost — Carousel Batch Preparation")
    print(f"Input:  {INPUT_DIR}")
    print(f"Output: {OUTPUT_ROOT}")
    print()

    sources = _collect_sources()
    if not sources:
        print("[error] No photo files found in input folder. Exiting.", file=sys.stderr)
        sys.exit(1)

    print(f"Found {len(sources)} photo file(s) in raw_photos.")
    print(f"Need {TOTAL_NEEDED} ({CAROUSELS} carousels × {IMAGES_PER_CAROUSEL} images). "
          f"{'OK' if len(sources) >= TOTAL_NEEDED else 'WARNING: not enough files — some slots will be skipped'}.")
    print(f"Selection: {TOTAL_NEEDED} evenly-spaced picks across all {len(sources)} files, "
          f"assigned round-robin so each carousel draws from different parts of the folder.")
    print()

    assignments = _select_diverse(sources)

    print("Source mapping:")
    for carousel_name, slot_name, src in assignments:
        src_label = src.name if src else "(no source — skipped)"
        print(f"  {carousel_name}/{slot_name} <- {src_label}")
    print()

    # Create output dirs
    for c in range(CAROUSELS):
        (OUTPUT_ROOT / f"carousel-{c + 1:03d}").mkdir(parents=True, exist_ok=True)

    # Process each slot
    with tempfile.TemporaryDirectory(prefix="instaAutoPost_carousels_") as tmpdir:
        for carousel_name, slot_name, src in assignments:
            dest = OUTPUT_ROOT / carousel_name / slot_name
            label = f"{carousel_name}/{slot_name}"

            if src is None:
                reason = "no source file available"
                print(f"  [{label}] skipped — {reason}")
                result.skipped.append(label)
                continue

            # Use a temp staging path so a partial write never lands in the output folder.
            tmp_dest = Path(tmpdir) / f"{carousel_name}_{slot_name}"

            print(f"  [{label}] converting {src.name} …", end=" ", flush=True)
            ok, err = _convert_to_jpg(src, tmp_dest)
            if not ok:
                print(f"FAILED")
                print(f"         reason: {err}", file=sys.stderr)
                result.failed.append((label, err))
                continue

            try:
                shutil.move(str(tmp_dest), dest)
            except OSError as exc:
                print(f"FAILED")
                print(f"         move error: {exc}", file=sys.stderr)
                result.failed.append((label, str(exc)))
                continue

            size_kb = round(dest.stat().st_size / 1024)
            print(f"OK ({size_kb} KB)")
            result.created.append(f"{label} <- {src.name}")

    _print_summary(result, time.monotonic() - t0)


if __name__ == "__main__":
    main()

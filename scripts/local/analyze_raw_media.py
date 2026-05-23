#!/usr/bin/env python3
"""
analyze_raw_media.py — Read-only local media analyzer for InstaAutoPost travel content.

Scans raw video and photo input folders, classifies each file as an Instagram
candidate type, and writes CSV manifests plus a plain-text summary to a reports
folder.  No files are modified, moved, deleted, converted, uploaded, or published.

Usage:
    python3 scripts/local/analyze_raw_media.py

Outputs (created inside ~/Desktop/InstaAutoPost_Travel_Content/reports/):
    raw_video_manifest.csv
    raw_photo_manifest.csv
    raw_media_summary.txt
"""

import csv
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
CONTENT_ROOT = Path.home() / "Desktop" / "InstaAutoPost_Travel_Content"

INPUT_FOLDERS = {
    "raw_videos": CONTENT_ROOT / "raw_videos",
    "raw_live_photo_videos": CONTENT_ROOT / "raw_live_photo_videos",
    "raw_photos": CONTENT_ROOT / "raw_photos",
}

REPORTS_DIR = CONTENT_ROOT / "reports"

VIDEO_MANIFEST = REPORTS_DIR / "raw_video_manifest.csv"
PHOTO_MANIFEST = REPORTS_DIR / "raw_photo_manifest.csv"
SUMMARY_FILE = REPORTS_DIR / "raw_media_summary.txt"

# ---------------------------------------------------------------------------
# Extension sets
# ---------------------------------------------------------------------------
VIDEO_EXTENSIONS = {".mp4", ".mov", ".m4v", ".avi", ".mkv", ".webm", ".3gp"}
PHOTO_EXTENSIONS = {".jpg", ".jpeg", ".heic", ".png", ".tiff", ".tif", ".webp"}

# Live Photo companion clips are short MOV files exported alongside HEIC stills.
# Apple typically names them with the same base name as the HEIC.
LIVE_PHOTO_MAX_DURATION_S = 4.0  # seconds; Apple Live Photos are ≤ 3 s

# ---------------------------------------------------------------------------
# Instagram dimension/duration constraints (Graph API v19+)
# ---------------------------------------------------------------------------
REEL_MIN_DURATION_S = 3.0
REEL_MAX_DURATION_S = 90.0
REEL_MIN_ASPECT = 9 / 16 - 0.02   # allow small float error
REEL_MAX_ASPECT = 9 / 16 + 0.02

VIDEO_POST_MAX_DURATION_S = 60.0

FFPROBE_BIN = "ffprobe"  # resolved via PATH; /opt/homebrew/bin is on PATH by default


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mb(path: Path) -> float:
    """Return file size in MB, rounded to 2 decimal places."""
    return round(path.stat().st_size / (1024 * 1024), 2)


def _run_ffprobe(path: Path) -> dict | None:
    """
    Run ffprobe on *path* and return the parsed JSON output, or None on error.
    Errors are printed to stderr but never raise so the scan continues.
    """
    cmd = [
        FFPROBE_BIN,
        "-v", "quiet",
        "-print_format", "json",
        "-show_streams",
        "-show_format",
        str(path),
    ]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            print(
                f"  [ffprobe error] {path.name}: {result.stderr.strip()[:120]}",
                file=sys.stderr,
            )
            return None
        return json.loads(result.stdout)
    except FileNotFoundError:
        print(
            "  [error] ffprobe not found. Install ffmpeg: brew install ffmpeg",
            file=sys.stderr,
        )
        return None
    except subprocess.TimeoutExpired:
        print(f"  [ffprobe timeout] {path.name}", file=sys.stderr)
        return None
    except json.JSONDecodeError as exc:
        print(f"  [ffprobe json error] {path.name}: {exc}", file=sys.stderr)
        return None


def _video_stream(probe: dict) -> dict | None:
    """Return the first video stream dict from an ffprobe result."""
    for stream in probe.get("streams", []):
        if stream.get("codec_type") == "video":
            return stream
    return None


def _orientation(width: int, height: int) -> str:
    if width == height:
        return "square"
    return "vertical" if height > width else "horizontal"


def _aspect_ratio(width: int, height: int) -> float:
    return width / height if height else 0.0


# ---------------------------------------------------------------------------
# Classification logic
# ---------------------------------------------------------------------------

def _classify_video(
    duration_s: float,
    width: int,
    height: int,
    folder_key: str,
) -> tuple[str, str]:
    """Return (candidate_type, notes)."""
    notes_parts: list[str] = []
    aspect = _aspect_ratio(width, height)

    if folder_key == "raw_live_photo_videos":
        if duration_s <= LIVE_PHOTO_MAX_DURATION_S:
            return "live_photo_clip_candidate", "short clip from raw_live_photo_videos folder"
        notes_parts.append("in live_photo_videos folder but duration > 4 s")

    if duration_s <= LIVE_PHOTO_MAX_DURATION_S and folder_key == "raw_videos":
        notes_parts.append(f"very short ({duration_s:.1f}s); may be a Live Photo clip")

    is_vertical = REEL_MIN_ASPECT <= aspect <= REEL_MAX_ASPECT
    if REEL_MIN_DURATION_S <= duration_s <= REEL_MAX_DURATION_S and is_vertical:
        return "reel_candidate", "; ".join(notes_parts) if notes_parts else ""

    if duration_s <= VIDEO_POST_MAX_DURATION_S:
        if not is_vertical:
            notes_parts.append(
                f"aspect {aspect:.3f} not 9:16; "
                "crop/reframe needed for Reel"
            )
        return "video_post_candidate", "; ".join(notes_parts)

    notes_parts.append(f"duration {duration_s:.1f}s exceeds 60 s video post limit")
    return "review_manually", "; ".join(notes_parts)


def _classify_photo(path: Path) -> tuple[str, str]:
    """Return (candidate_type, notes) for a photo file."""
    ext = path.suffix.lower()
    notes = ""
    if ext == ".heic":
        notes = "HEIC; convert to JPG before upload"
    elif ext not in {".jpg", ".jpeg", ".png"}:
        notes = f"{ext} may need conversion"
    return "carousel_candidate", notes


# ---------------------------------------------------------------------------
# Scanning
# ---------------------------------------------------------------------------

def scan_videos() -> list[dict]:
    rows: list[dict] = []

    for folder_key in ("raw_videos", "raw_live_photo_videos"):
        folder = INPUT_FOLDERS[folder_key]
        if not folder.exists():
            print(f"  [skip] folder not found: {folder}")
            continue

        files = sorted(
            f for f in folder.rglob("*")
            if f.is_file() and f.suffix.lower() in VIDEO_EXTENSIONS
        )
        print(f"  {folder_key}: {len(files)} video file(s) found")

        for f in files:
            size_mb = _mb(f)
            probe = _run_ffprobe(f)

            if probe is None:
                rows.append({
                    "filename": f.name,
                    "full_path": str(f),
                    "folder_source": folder_key,
                    "extension": f.suffix.lower(),
                    "file_size_mb": size_mb,
                    "duration_seconds": "",
                    "width": "",
                    "height": "",
                    "orientation": "",
                    "candidate_type": "review_manually",
                    "notes": "ffprobe failed; inspect manually",
                })
                continue

            vs = _video_stream(probe)
            fmt = probe.get("format", {})

            duration_s = float(fmt.get("duration") or (vs or {}).get("duration") or 0)
            width = int((vs or {}).get("width") or 0)
            height = int((vs or {}).get("height") or 0)

            # Some MOV files encode rotation in side-data; swap w/h if rotated 90/270.
            rotation = 0
            if vs:
                side_data = vs.get("side_data_list", [])
                for sd in side_data:
                    if sd.get("side_data_type") == "Display Matrix":
                        rotation = abs(int(sd.get("rotation", 0)))
            if rotation in (90, 270) and width and height:
                width, height = height, width

            orientation = _orientation(width, height) if (width and height) else ""
            candidate_type, notes = _classify_video(duration_s, width, height, folder_key)

            rows.append({
                "filename": f.name,
                "full_path": str(f),
                "folder_source": folder_key,
                "extension": f.suffix.lower(),
                "file_size_mb": size_mb,
                "duration_seconds": round(duration_s, 2),
                "width": width,
                "height": height,
                "orientation": orientation,
                "candidate_type": candidate_type,
                "notes": notes,
            })

    return rows


def scan_photos() -> list[dict]:
    rows: list[dict] = []
    folder = INPUT_FOLDERS["raw_photos"]

    if not folder.exists():
        print(f"  [skip] folder not found: {folder}")
        return rows

    files = sorted(
        f for f in folder.rglob("*")
        if f.is_file() and f.suffix.lower() in PHOTO_EXTENSIONS
    )
    print(f"  raw_photos: {len(files)} photo file(s) found")

    for f in files:
        candidate_type, notes = _classify_photo(f)
        rows.append({
            "filename": f.name,
            "full_path": str(f),
            "extension": f.suffix.lower(),
            "file_size_mb": _mb(f),
            "candidate_type": candidate_type,
            "notes": notes,
        })

    return rows


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

VIDEO_CSV_FIELDS = [
    "filename",
    "full_path",
    "folder_source",
    "extension",
    "file_size_mb",
    "duration_seconds",
    "width",
    "height",
    "orientation",
    "candidate_type",
    "notes",
]

PHOTO_CSV_FIELDS = [
    "filename",
    "full_path",
    "extension",
    "file_size_mb",
    "candidate_type",
    "notes",
]


def write_csv(path: Path, fields: list[str], rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _count_by_type(rows: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for r in rows:
        ct = r.get("candidate_type", "unknown")
        counts[ct] = counts.get(ct, 0) + 1
    return counts


def write_summary(
    video_rows: list[dict],
    photo_rows: list[dict],
    elapsed_s: float,
) -> str:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        "=" * 60,
        "InstaAutoPost — Raw Media Analysis Summary",
        f"Generated: {ts}",
        f"Elapsed:   {elapsed_s:.1f}s",
        "=" * 60,
        "",
        f"VIDEO FILES SCANNED: {len(video_rows)}",
    ]

    for ct, count in sorted(_count_by_type(video_rows).items()):
        lines.append(f"  {ct:<30} {count:>4}")

    lines += [
        "",
        f"PHOTO FILES SCANNED: {len(photo_rows)}",
    ]

    for ct, count in sorted(_count_by_type(photo_rows).items()):
        lines.append(f"  {ct:<30} {count:>4}")

    lines += [
        "",
        "OUTPUT FILES",
        f"  {VIDEO_MANIFEST}",
        f"  {PHOTO_MANIFEST}",
        f"  {SUMMARY_FILE}",
        "",
        "SAFETY",
        "  No files were modified, moved, deleted, converted,",
        "  uploaded, or published by this script.",
        "=" * 60,
    ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    import time as _time

    t0 = _time.monotonic()

    print("InstaAutoPost — Raw Media Analyzer")
    print(f"Content root: {CONTENT_ROOT}")
    print()

    # Warn if any input folder is missing but continue.
    for key, folder in INPUT_FOLDERS.items():
        if not folder.exists():
            print(f"[warning] Input folder does not exist: {folder}", file=sys.stderr)

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    print("Scanning videos...")
    video_rows = scan_videos()

    print("Scanning photos...")
    photo_rows = scan_photos()

    print()
    print("Writing reports...")
    write_csv(VIDEO_MANIFEST, VIDEO_CSV_FIELDS, video_rows)
    write_csv(PHOTO_MANIFEST, PHOTO_CSV_FIELDS, photo_rows)

    elapsed = _time.monotonic() - t0
    summary_text = write_summary(video_rows, photo_rows, elapsed)

    with SUMMARY_FILE.open("w", encoding="utf-8") as fh:
        fh.write(summary_text)
        fh.write("\n")

    print()
    print(summary_text)


if __name__ == "__main__":
    main()

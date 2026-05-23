#!/usr/bin/env python3
"""
prepare_test_video_batch.py — Safe local video preparation for InstaAutoPost travel test batch.

Reads video files from ~/Desktop/InstaAutoPost_Travel_Content/selected_videos,
converts the first 3 into Instagram-ready Reels (1080x1920 vertical MP4) and
the first 3 into video post MP4 files.

Original files are never modified, moved, or deleted.
No network calls. No Supabase. No Instagram actions.

Usage:
    python3 scripts/local/prepare_test_video_batch.py

Outputs (created inside ~/Desktop/InstaAutoPost_Travel_Content/):
    ready_reels/reel-001.mp4
    ready_reels/reel-002.mp4
    ready_reels/reel-003.mp4
    ready_video_posts/video-post-001.mp4
    ready_video_posts/video-post-002.mp4
    ready_video_posts/video-post-003.mp4
"""

import json
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
CONTENT_ROOT = Path.home() / "Desktop" / "InstaAutoPost_Travel_Content"
INPUT_DIR = CONTENT_ROOT / "selected_videos"
REELS_OUT = CONTENT_ROOT / "ready_reels"
POSTS_OUT = CONTENT_ROOT / "ready_video_posts"

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
VIDEO_EXTENSIONS = {".mp4", ".mov", ".m4v", ".avi", ".mkv", ".webm", ".3gp"}

REEL_WIDTH = 1080
REEL_HEIGHT = 1920

# Trim target for Reels: 10–20 s desired. If source > 20 s, trim to 15 s.
REEL_MAX_S = 20.0
REEL_TRIM_S = 15.0

# Trim target for Video Posts: 20–45 s desired. If source > 45 s, trim to 30 s.
POST_MAX_S = 45.0
POST_TRIM_S = 30.0

BATCH_SIZE = 3

FFPROBE_BIN = "ffprobe"
FFMPEG_BIN = "ffmpeg"


# ---------------------------------------------------------------------------
# Probe
# ---------------------------------------------------------------------------

@dataclass
class VideoInfo:
    path: Path
    width: int
    height: int
    duration_s: float
    has_audio: bool


def _probe(path: Path) -> "VideoInfo | None":
    cmd = [
        FFPROBE_BIN,
        "-v", "quiet",
        "-print_format", "json",
        "-show_streams",
        "-show_format",
        str(path),
    ]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    except FileNotFoundError:
        print("[error] ffprobe not found — install with: brew install ffmpeg", file=sys.stderr)
        return None
    except subprocess.TimeoutExpired:
        print(f"[error] ffprobe timeout on {path.name}", file=sys.stderr)
        return None

    if r.returncode != 0:
        print(f"[error] ffprobe failed on {path.name}: {r.stderr.strip()[:120]}", file=sys.stderr)
        return None

    try:
        data = json.loads(r.stdout)
    except json.JSONDecodeError as exc:
        print(f"[error] ffprobe JSON parse error on {path.name}: {exc}", file=sys.stderr)
        return None

    video_stream = None
    has_audio = False
    for stream in data.get("streams", []):
        codec_type = stream.get("codec_type")
        if codec_type == "video" and video_stream is None:
            video_stream = stream
        if codec_type == "audio":
            has_audio = True

    if video_stream is None:
        print(f"[error] no video stream in {path.name}", file=sys.stderr)
        return None

    fmt = data.get("format", {})
    duration_s = float(fmt.get("duration") or video_stream.get("duration") or 0)
    width = int(video_stream.get("width") or 0)
    height = int(video_stream.get("height") or 0)

    # Correct logical dimensions for videos stored with rotation metadata
    # (e.g. iPhone portrait clips stored as landscape with rotation=90).
    # ffmpeg applies autorotate by default, so the filter chain sees logical dims.
    for sd in video_stream.get("side_data_list", []):
        if sd.get("side_data_type") == "Display Matrix":
            rotation = abs(int(sd.get("rotation", 0)))
            if rotation in (90, 270) and width and height:
                width, height = height, width
            break

    if not width or not height:
        print(f"[error] could not determine dimensions for {path.name}", file=sys.stderr)
        return None

    return VideoInfo(
        path=path,
        width=width,
        height=height,
        duration_s=duration_s,
        has_audio=has_audio,
    )


# ---------------------------------------------------------------------------
# Filter construction
# ---------------------------------------------------------------------------

def _reel_vf(info: VideoInfo) -> str:
    """
    Return an ffmpeg -vf filter string that produces 1080x1920.

    Horizontal / square source: center-crop a 9:16 column, then scale up.
    Vertical source:            scale to fit, pad black bars for any remainder.
    """
    if info.width >= info.height:
        # Center-crop a 9:16 slice (full height, cropped width) then scale.
        return (
            "crop=ih*9/16:ih:(iw-ih*9/16)/2:0,"
            f"scale={REEL_WIDTH}:{REEL_HEIGHT}"
        )
    else:
        # Already taller than wide — scale down, add black bars if the aspect
        # is not exactly 9:16.
        return (
            f"scale={REEL_WIDTH}:{REEL_HEIGHT}:force_original_aspect_ratio=decrease,"
            f"pad={REEL_WIDTH}:{REEL_HEIGHT}:(ow-iw)/2:(oh-ih)/2:color=black"
        )


def _trim_args(duration_s: float, max_s: float, trim_s: float) -> list[str]:
    """Return ['-t', '<seconds>'] if the source exceeds max_s, else []."""
    if duration_s > max_s:
        return ["-t", str(trim_s)]
    return []


# ---------------------------------------------------------------------------
# Encoding
# ---------------------------------------------------------------------------

def _run_ffmpeg(args: list[str]) -> tuple[bool, str]:
    """Run ffmpeg with *args*. Returns (success, error_snippet)."""
    cmd = [FFMPEG_BIN, "-y"] + args
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    except FileNotFoundError:
        return False, "ffmpeg not found — install with: brew install ffmpeg"
    except subprocess.TimeoutExpired:
        return False, "ffmpeg timed out after 5 minutes"

    if r.returncode != 0:
        return False, r.stderr.strip()[-200:]
    return True, ""


def encode_reel(info: VideoInfo, out: Path) -> tuple[bool, str]:
    vf = _reel_vf(info)
    trim = _trim_args(info.duration_s, REEL_MAX_S, REEL_TRIM_S)
    audio = ["-c:a", "aac", "-b:a", "128k"] if info.has_audio else ["-an"]

    args = (
        ["-i", str(info.path)]
        + trim
        + [
            "-vf", vf,
            "-c:v", "libx264",
            "-crf", "23",
            "-preset", "medium",
            "-r", "30",
            "-pix_fmt", "yuv420p",
        ]
        + audio
        + ["-movflags", "+faststart", str(out)]
    )
    return _run_ffmpeg(args)


def encode_post(info: VideoInfo, out: Path) -> tuple[bool, str]:
    trim = _trim_args(info.duration_s, POST_MAX_S, POST_TRIM_S)
    audio = ["-c:a", "aac", "-b:a", "128k"] if info.has_audio else ["-an"]

    args = (
        ["-i", str(info.path)]
        + trim
        + [
            "-c:v", "libx264",
            "-crf", "23",
            "-preset", "medium",
            "-pix_fmt", "yuv420p",
        ]
        + audio
        + ["-movflags", "+faststart", str(out)]
    )
    return _run_ffmpeg(args)


# ---------------------------------------------------------------------------
# Result tracking
# ---------------------------------------------------------------------------

@dataclass
class BatchResult:
    created: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    failed: list[tuple[str, str]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _collect_sources() -> list[Path]:
    if not INPUT_DIR.exists():
        print(f"[error] Input folder not found: {INPUT_DIR}", file=sys.stderr)
        return []
    return sorted(
        f for f in INPUT_DIR.iterdir()
        if f.is_file() and f.suffix.lower() in VIDEO_EXTENSIONS
    )


def _size_mb(path: Path) -> float:
    return round(path.stat().st_size / (1024 * 1024), 2)


def _print_summary(result: BatchResult, elapsed_s: float) -> None:
    sep = "=" * 60
    print()
    print(sep)
    print("InstaAutoPost — Video Batch Preparation Summary")
    print(f"Elapsed: {elapsed_s:.1f}s")
    print(sep)

    print(f"\nCREATED ({len(result.created)})")
    if result.created:
        for p in result.created:
            print(f"  {p}")
    else:
        print("  (none)")

    print(f"\nSKIPPED ({len(result.skipped)})")
    if result.skipped:
        for s in result.skipped:
            print(f"  {s}")
    else:
        print("  (none)")

    print(f"\nFAILED ({len(result.failed)})")
    if result.failed:
        for name, reason in result.failed:
            print(f"  {name}: {reason}")
    else:
        print("  (none)")

    print()
    print("SAFETY")
    print("  Original files in selected_videos were not modified.")
    print("  No uploads, no publishing, no network calls performed.")
    print(sep)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def _process_batch(
    sources: list[Path],
    batch_type: str,
    out_dir: Path,
    name_prefix: str,
    encode_fn,
    result: BatchResult,
) -> None:
    print(f"--- Processing {batch_type} ---")
    for i in range(BATCH_SIZE):
        label = f"{name_prefix}-{i+1:03d}.mp4"
        out = out_dir / label

        if i >= len(sources):
            reason = f"no source file available (only {len(sources)} file(s) found)"
            print(f"  [{label}] skipped — {reason}")
            result.skipped.append(label)
            continue

        src = sources[i]
        print(f"  [{label}] probing {src.name} …")
        info = _probe(src)
        if info is None:
            result.failed.append((label, f"ffprobe failed on {src.name}"))
            continue

        orientation = "vertical" if info.height > info.width else "horizontal/square"
        print(f"         {info.width}x{info.height} ({orientation}), {info.duration_s:.1f}s source")

        ok, err = encode_fn(info, out)
        if ok:
            print(f"         created → {out.name} ({_size_mb(out)} MB)")
            result.created.append(str(out))
        else:
            snippet = err[:120]
            print(f"         [failed] {snippet}", file=sys.stderr)
            result.failed.append((label, snippet))

    print()


def main() -> None:
    t0 = time.monotonic()
    result = BatchResult()

    print("InstaAutoPost — Video Batch Preparation")
    print(f"Input:  {INPUT_DIR}")
    print(f"Reels:  {REELS_OUT}")
    print(f"Posts:  {POSTS_OUT}")
    print()

    sources = _collect_sources()
    if not sources:
        print("[error] No video files found in input folder. Exiting.", file=sys.stderr)
        sys.exit(1)

    print(f"Found {len(sources)} video file(s):")
    for f in sources:
        print(f"  {f.name}")
    print()

    # Each source is used exactly once.
    # Slots 0-2 → Reels; slots 3-5 → Video Posts (non-overlapping).
    reel_sources = sources[:BATCH_SIZE]
    post_sources = sources[BATCH_SIZE:BATCH_SIZE * 2]

    print("Source mapping:")
    for i in range(BATCH_SIZE):
        src = reel_sources[i].name if i < len(reel_sources) else "(no source)"
        print(f"  reel-{i+1:03d}.mp4        <- {src}")
    for i in range(BATCH_SIZE):
        src = post_sources[i].name if i < len(post_sources) else "(no source)"
        print(f"  video-post-{i+1:03d}.mp4  <- {src}")
    print()

    REELS_OUT.mkdir(parents=True, exist_ok=True)
    POSTS_OUT.mkdir(parents=True, exist_ok=True)

    _process_batch(reel_sources, "Reels", REELS_OUT, "reel", encode_reel, result)
    _process_batch(post_sources, "Video Posts", POSTS_OUT, "video-post", encode_post, result)

    _print_summary(result, time.monotonic() - t0)


if __name__ == "__main__":
    main()

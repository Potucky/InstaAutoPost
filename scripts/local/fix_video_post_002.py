#!/usr/bin/env python3
"""
fix_video_post_002.py — One-shot fix for missing Video Post 002.

Compresses video-post-002.mp4, uploads only the compressed file to
Supabase Storage (instaautopost-media bucket), and inserts exactly one
record into public.ig_content_library.

Safety:
  - No Instagram publishing.
  - No GitHub Actions triggered.
  - Source file is never modified.
  - Only one upload and one DB insert are attempted.
  - Default: DRY RUN. Pass --execute to write.

Usage:
    python3 scripts/local/fix_video_post_002.py            # dry run
    python3 scripts/local/fix_video_post_002.py --execute  # real upload + insert

Required env vars (--execute only):
    SUPABASE_URL
    SUPABASE_SERVICE_ROLE_KEY
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
SOURCE = Path.home() / "Desktop" / "InstaAutoPost_Travel_Content" / "ready_video_posts" / "video-post-002.mp4"
COMPRESSED = Path.home() / "Desktop" / "InstaAutoPost_Travel_Content" / "ready_video_posts" / "video-post-002-compressed.mp4"

TARGET_MB = 40          # compress to under 40 MB (well below 45 MB Supabase limit)
TRIM_SECONDS = 10       # max trim if bitrate would be too low
MIN_VIDEO_KBPS = 600    # minimum acceptable video bitrate before falling back to trim

BUCKET = "instaautopost-media"
STORAGE_PREFIX = "test-import"
TABLE = "ig_content_library"
RECORD_TITLE = "Video Post 002"


# ---------------------------------------------------------------------------
# ffprobe helpers
# ---------------------------------------------------------------------------

def get_duration(path: Path) -> float:
    cmd = [
        "ffprobe", "-v", "quiet", "-print_format", "json",
        "-show_streams", str(path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    data = json.loads(result.stdout)
    for stream in data.get("streams", []):
        if stream.get("codec_type") == "video":
            dur = stream.get("duration")
            if dur:
                return float(dur)
    raise RuntimeError("Could not read video duration from ffprobe.")


# ---------------------------------------------------------------------------
# Compression
# ---------------------------------------------------------------------------

def compress(dry_run: bool) -> tuple[bool, str]:
    """Compress source → COMPRESSED. Returns (ok, message)."""
    if not SOURCE.exists():
        return False, f"Source not found: {SOURCE}"

    if COMPRESSED.exists():
        size_mb = COMPRESSED.stat().st_size / (1024 * 1024)
        print(f"[compress] Compressed file already exists ({size_mb:.1f} MB): {COMPRESSED}")
        if size_mb < 45:
            print("[compress] Reusing existing compressed file — skipping re-encode.")
            return True, "reused"
        print("[compress] Existing file is >= 45 MB — re-encoding.")

    duration = get_duration(SOURCE)
    source_mb = SOURCE.stat().st_size / (1024 * 1024)
    print(f"[compress] Source duration: {duration:.1f}s  size: {source_mb:.1f} MB")

    # Determine whether to trim or just reduce bitrate.
    # Target bitrate (kbps) = target_size_bits / duration_seconds / 1000
    audio_kbps = 128
    target_bits = TARGET_MB * 8 * 1024 * 1024
    video_kbps = int(target_bits / duration / 1000) - audio_kbps

    use_trim = False
    trim_duration = duration

    if video_kbps < MIN_VIDEO_KBPS:
        print(f"[compress] Calculated video bitrate ({video_kbps} kbps) is below minimum "
              f"({MIN_VIDEO_KBPS} kbps) — trimming to {TRIM_SECONDS}s.")
        use_trim = True
        trim_duration = TRIM_SECONDS
        target_bits = TARGET_MB * 8 * 1024 * 1024
        video_kbps = int(target_bits / TRIM_SECONDS / 1000) - audio_kbps

    print(f"[compress] Target: video={video_kbps} kbps  audio={audio_kbps} kbps"
          + (f"  trim={TRIM_SECONDS}s" if use_trim else ""))

    cmd = ["ffmpeg", "-y", "-i", str(SOURCE)]
    if use_trim:
        cmd += ["-t", str(trim_duration)]
    cmd += [
        "-c:v", "libx264",
        "-b:v", f"{video_kbps}k",
        "-c:a", "aac",
        "-b:a", f"{audio_kbps}k",
        "-movflags", "+faststart",
        "-f", "mp4",
        str(COMPRESSED),
    ]

    print(f"[compress] Running ffmpeg …")
    if dry_run:
        print(f"[compress] DRY RUN — would run: {' '.join(cmd)}")
        return True, "dry_run"

    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        return False, f"ffmpeg failed:\n{proc.stderr[-800:]}"

    if not COMPRESSED.exists():
        return False, "ffmpeg exited 0 but output file not found."

    out_mb = COMPRESSED.stat().st_size / (1024 * 1024)
    print(f"[compress] Output: {COMPRESSED} ({out_mb:.1f} MB)")

    if out_mb >= 45:
        return False, f"Compressed file is {out_mb:.1f} MB — still >= 45 MB. Aborting upload."

    return True, "ok"


# ---------------------------------------------------------------------------
# Supabase helpers
# ---------------------------------------------------------------------------

def _build_client():
    from supabase import create_client
    url = os.environ.get("SUPABASE_URL", "").strip()
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    if not url or not key:
        print(
            "\n[error] Missing required env vars. Run with:\n\n"
            "  SUPABASE_URL='...' SUPABASE_SERVICE_ROLE_KEY='...' "
            "python3 scripts/local/fix_video_post_002.py --execute\n",
            file=sys.stderr,
        )
        sys.exit(1)
    return create_client(url, key), url


def _public_url(supabase_url: str, storage_path: str) -> str:
    return f"{supabase_url.rstrip('/')}/storage/v1/object/public/{BUCKET}/{storage_path}"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    dry_run = "--execute" not in sys.argv
    mode = "DRY RUN" if dry_run else "EXECUTE"
    t0 = time.monotonic()

    print(f"InstaAutoPost — fix_video_post_002 [{mode}]")
    if dry_run:
        print("  Pass --execute to perform real compression, upload, and DB insert.\n")

    # Env var check (always, so the user knows early).
    supabase_url = os.environ.get("SUPABASE_URL", "").strip()
    service_role_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    if not dry_run and (not supabase_url or not service_role_key):
        print(
            "\n[error] Missing required env vars. Run with:\n\n"
            "  SUPABASE_URL='...' SUPABASE_SERVICE_ROLE_KEY='...' "
            "python3 scripts/local/fix_video_post_002.py --execute\n",
            file=sys.stderr,
        )
        sys.exit(1)

    # -----------------------------------------------------------------------
    # Step 1: Compress
    # -----------------------------------------------------------------------
    print("\n--- Step 1: Compress ---")
    ok, compress_msg = compress(dry_run=dry_run)
    if not ok:
        print(f"[FAIL] Compression failed: {compress_msg}", file=sys.stderr)
        sys.exit(1)

    if dry_run:
        compressed_size = None
        storage_path = f"{STORAGE_PREFIX}/<timestamp>_video-post-002-compressed.mp4"
        public_url = _public_url(supabase_url or "<SUPABASE_URL>", storage_path)
    else:
        compressed_size = COMPRESSED.stat().st_size
        run_ts = int(t0)
        storage_path = f"{STORAGE_PREFIX}/{run_ts}_video-post-002-compressed.mp4"
        public_url = _public_url(supabase_url, storage_path)

    # -----------------------------------------------------------------------
    # Step 2: Upload
    # -----------------------------------------------------------------------
    print("\n--- Step 2: Upload to Supabase Storage ---")
    upload_attempted = 0
    upload_ok = False

    if dry_run:
        print(f"[upload] DRY RUN — would upload:")
        print(f"  local:   {COMPRESSED}")
        print(f"  bucket:  {BUCKET}")
        print(f"  path:    {storage_path}")
        print(f"  url:     {public_url}")
    else:
        upload_attempted = 1
        supabase, _ = _build_client()
        print(f"[upload] Uploading {COMPRESSED.name} ({compressed_size / (1024*1024):.1f} MB) …", end=" ", flush=True)
        try:
            data = COMPRESSED.read_bytes()
            supabase.storage.from_(BUCKET).upload(
                path=storage_path,
                file=data,
                file_options={"content-type": "video/mp4", "x-upsert": "false"},
            )
            print("OK")
            upload_ok = True
        except Exception as exc:
            print("FAILED")
            print(f"[error] Upload failed: {str(exc)[:400]}", file=sys.stderr)
            sys.exit(1)

    # -----------------------------------------------------------------------
    # Step 3: DB insert
    # -----------------------------------------------------------------------
    print("\n--- Step 3: Insert DB record ---")
    insert_attempted = 0
    insert_ok = False

    record = {
        "title": RECORD_TITLE,
        "media_type": "VIDEO",
        "content_status": "draft",
        "video_url": public_url,
        "file_size": compressed_size,
        "caption": "",
        "hashtags": [],
    }

    if dry_run:
        print(f"[db] DRY RUN — would insert into {TABLE}:")
        for k, v in record.items():
            print(f"  {k}: {v!r}")
    else:
        insert_attempted = 1
        try:
            supabase.table(TABLE).insert(record).execute()
            print(f"[db] Inserted: title={RECORD_TITLE!r}  media_type=VIDEO  status=draft")
            insert_ok = True
        except Exception as exc:
            print(f"[error] DB insert failed: {str(exc)[:400]}", file=sys.stderr)
            sys.exit(1)

    # -----------------------------------------------------------------------
    # Summary
    # -----------------------------------------------------------------------
    elapsed = time.monotonic() - t0
    sep = "=" * 60
    print(f"\n{sep}")
    print(f"InstaAutoPost — fix_video_post_002 Summary [{mode}]")
    print(f"Elapsed: {elapsed:.1f}s")
    print(sep)

    if dry_run:
        print("\nDRY RUN — no files written, no uploads, no DB inserts.")
        print(f"  compressed path (planned): {COMPRESSED}")
        print(f"  storage path (planned):    {storage_path}")
        print(f"  DB record (planned):       title={RECORD_TITLE!r}")
    else:
        print(f"\n  compressed file path:  {COMPRESSED}")
        print(f"  compressed file size:  {compressed_size / (1024*1024):.2f} MB ({compressed_size:,} bytes)")
        print(f"  uploaded storage path: {storage_path}")
        print(f"  inserted record title: {RECORD_TITLE!r}")
        print(f"\n  uploads attempted:  {upload_attempted}  (succeeded: {int(upload_ok)})")
        print(f"  inserts attempted:  {insert_attempted}  (succeeded: {int(insert_ok)})")
        print(f"  failed count:       {int(not upload_ok) + int(not insert_ok)}")

    print("\nSAFETY")
    print("  No Instagram publishing performed.")
    print("  No source file modified.")
    print("  No other content items touched.")
    print(sep)


if __name__ == "__main__":
    main()

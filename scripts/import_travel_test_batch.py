#!/usr/bin/env python3
"""
import_travel_test_batch.py — Safe batch importer for InstaAutoPost travel test content.

Uploads prepared local media files to the instaautopost-media Supabase Storage bucket
and inserts matching records into public.ig_content_library.

Default: DRY RUN — prints planned uploads and DB records. No writes performed.
Use --execute to perform real uploads and inserts.

Safety: No Instagram publishing. No GitHub Actions. No local file modification.

Carousel schema note:
  ig_content_library has a single video_url TEXT NOT NULL field — no image array.
  For carousels, all 7 images are uploaded to storage. Only 01.jpg gets a DB record
  (media_type='CAROUSEL', video_url=01.jpg public URL). Images 02–07 are stored but
  not linked in the DB. Full carousel publishing requires a future schema extension.

Usage:
    python3 scripts/import_travel_test_batch.py             # dry run
    python3 scripts/import_travel_test_batch.py --execute   # real upload + insert

Required env vars:
    SUPABASE_URL
    SUPABASE_SERVICE_ROLE_KEY
"""

import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from supabase import create_client, Client

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
CONTENT_ROOT = Path.home() / "Desktop" / "InstaAutoPost_Travel_Content"
REELS_DIR = CONTENT_ROOT / "ready_reels"
POSTS_DIR = CONTENT_ROOT / "ready_video_posts"
CAROUSELS_DIR = CONTENT_ROOT / "ready_carousels"

# ---------------------------------------------------------------------------
# Supabase constants
# ---------------------------------------------------------------------------
BUCKET = "instaautopost-media"
STORAGE_PREFIX = "test-import"
TABLE = "ig_content_library"

# ---------------------------------------------------------------------------
# Expected media inventory
# ---------------------------------------------------------------------------
EXPECTED_REELS = [f"reel-{i:03d}.mp4" for i in range(1, 4)]
EXPECTED_POSTS = [f"video-post-{i:03d}.mp4" for i in range(1, 4)]
EXPECTED_CAROUSELS = [f"carousel-{i:03d}" for i in range(1, 4)]
CAROUSEL_SLOTS = [f"{i:02d}.jpg" for i in range(1, 8)]

CONTENT_TYPE = {".mp4": "video/mp4", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}


# ---------------------------------------------------------------------------
# Plan
# ---------------------------------------------------------------------------

@dataclass
class UploadPlan:
    local_path: Path
    storage_path: str          # key inside the bucket
    content_type: str
    title: str
    media_type: str            # REEL | VIDEO | CAROUSEL | CAROUSEL_IMAGE
    create_db_record: bool     # False for CAROUSEL_IMAGE slots 02–07
    carousel_name: Optional[str] = None  # e.g. "carousel-001"


def _build_plan(run_ts: int) -> list[UploadPlan]:
    """
    Build the full upload plan deterministically from the run timestamp.
    No I/O is performed here — only path construction.
    """
    items: list[UploadPlan] = []

    for name in EXPECTED_REELS:
        items.append(UploadPlan(
            local_path=REELS_DIR / name,
            storage_path=f"{STORAGE_PREFIX}/{run_ts}_{name}",
            content_type="video/mp4",
            title=name.removesuffix(".mp4").replace("-", " ").title(),
            media_type="REEL",
            create_db_record=True,
        ))

    for name in EXPECTED_POSTS:
        items.append(UploadPlan(
            local_path=POSTS_DIR / name,
            storage_path=f"{STORAGE_PREFIX}/{run_ts}_{name}",
            content_type="video/mp4",
            title=name.removesuffix(".mp4").replace("-", " ").title(),
            media_type="VIDEO",
            create_db_record=True,
        ))

    for carousel_name in EXPECTED_CAROUSELS:
        for slot_idx, slot in enumerate(CAROUSEL_SLOTS):
            is_primary = slot_idx == 0
            items.append(UploadPlan(
                local_path=CAROUSELS_DIR / carousel_name / slot,
                storage_path=f"{STORAGE_PREFIX}/{run_ts}_{carousel_name}_{slot}",
                content_type="image/jpeg",
                title=carousel_name.replace("-", " ").title(),
                media_type="CAROUSEL" if is_primary else "CAROUSEL_IMAGE",
                create_db_record=is_primary,
                carousel_name=carousel_name,
            ))

    return items


# ---------------------------------------------------------------------------
# Supabase helpers
# ---------------------------------------------------------------------------

def _build_client() -> Client:
    url = os.environ.get("SUPABASE_URL", "").strip()
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    if not url or not key:
        print("[error] SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required.", file=sys.stderr)
        sys.exit(1)
    return create_client(url, key)


def _public_url(supabase_url: str, storage_path: str) -> str:
    return f"{supabase_url.rstrip('/')}/storage/v1/object/public/{BUCKET}/{storage_path}"


def _upload_file(supabase: Client, item: UploadPlan) -> tuple[bool, str]:
    try:
        data = item.local_path.read_bytes()
    except OSError as exc:
        return False, f"read error: {exc}"

    try:
        supabase.storage.from_(BUCKET).upload(
            path=item.storage_path,
            file=data,
            file_options={"content-type": item.content_type, "x-upsert": "false"},
        )
        return True, ""
    except Exception as exc:
        return False, str(exc)[:300]


def _insert_record(supabase: Client, item: UploadPlan, public_url: str) -> tuple[bool, str]:
    record = {
        "title": item.title,
        "video_url": public_url,
        "media_type": item.media_type,
        "content_status": "draft",
        "file_size": item.local_path.stat().st_size,
        "caption": "",
        "hashtags": [],
    }
    try:
        supabase.table(TABLE).insert(record).execute()
        return True, ""
    except Exception as exc:
        return False, str(exc)[:300]


# ---------------------------------------------------------------------------
# Result tracking
# ---------------------------------------------------------------------------

@dataclass
class ImportResult:
    planned: list[str] = field(default_factory=list)
    uploaded: list[str] = field(default_factory=list)
    inserted: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    failed: list[tuple[str, str]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

def _print_summary(result: ImportResult, dry_run: bool, elapsed_s: float) -> None:
    mode = "DRY RUN" if dry_run else "EXECUTE"
    sep = "=" * 60
    print()
    print(sep)
    print(f"InstaAutoPost — Travel Test Batch Import Summary [{mode}]")
    print(f"Elapsed: {elapsed_s:.1f}s")
    print(sep)

    if dry_run:
        print(f"\nPLANNED FILES ({len(result.planned)})")
        for p in result.planned or ["(none)"]:
            print(f"  {p}")
    else:
        print(f"\nUPLOADED ({len(result.uploaded)})")
        for p in result.uploaded or ["(none)"]:
            print(f"  {p}")

        print(f"\nINSERTED RECORDS ({len(result.inserted)})")
        for r in result.inserted or ["(none)"]:
            print(f"  {r}")

    print(f"\nSKIPPED ({len(result.skipped)})")
    for s in result.skipped or ["(none)"]:
        print(f"  {s}")

    print(f"\nFAILED ({len(result.failed)})")
    if result.failed:
        for name, reason in result.failed:
            print(f"  {name}: {reason}")
    else:
        print("  (none)")

    print()
    print("SAFETY")
    print("  No Instagram publishing performed.")
    print("  No local source files modified.")
    if dry_run:
        print("  DRY RUN: no uploads or DB inserts were performed.")
    print(sep)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    dry_run = "--execute" not in sys.argv
    t0 = time.monotonic()
    run_ts = int(t0)
    result = ImportResult()

    mode_label = "DRY RUN" if dry_run else "EXECUTE"
    print(f"InstaAutoPost — Travel Test Batch Import [{mode_label}]")
    if dry_run:
        print("  Pass --execute to perform real uploads and DB inserts.")
    print()

    supabase_url = os.environ.get("SUPABASE_URL", "").strip()

    plan = _build_plan(run_ts)

    # ---------------------------------------------------------------------------
    # File availability check
    # ---------------------------------------------------------------------------
    print("Checking local files …")
    available: set[str] = set()
    for item in plan:
        rel = str(item.local_path.relative_to(CONTENT_ROOT))
        if not item.local_path.exists():
            print(f"  [missing] {rel}")
            result.skipped.append(rel)
        else:
            size_mb = round(item.local_path.stat().st_size / (1024 * 1024), 2)
            print(f"  [ok]      {rel} ({size_mb} MB)")
            available.add(rel)
            result.planned.append(rel)
    print()

    # ---------------------------------------------------------------------------
    # Planned mapping printout
    # ---------------------------------------------------------------------------
    url_base = supabase_url or "<SUPABASE_URL>"
    print("Planned storage mapping:")
    for item in plan:
        rel = str(item.local_path.relative_to(CONTENT_ROOT))
        if rel not in available:
            continue
        pub_url = _public_url(url_base, item.storage_path)
        db_note = "  [+DB record]" if item.create_db_record else ""
        print(f"  {rel}")
        print(f"    -> {item.storage_path}{db_note}")
        if item.create_db_record:
            print(f"    -> video_url: {pub_url}")
    print()

    if dry_run:
        print("Planned DB records (ig_content_library):")
        for item in plan:
            if not item.create_db_record:
                continue
            rel = str(item.local_path.relative_to(CONTENT_ROOT))
            if rel not in available:
                continue
            pub_url = _public_url(url_base, item.storage_path)
            print(f"  title={item.title!r}  media_type={item.media_type}  "
                  f"status=draft  video_url={pub_url}")
        print()
        print("CAROUSEL NOTE: schema has single video_url field — only 01.jpg per carousel")
        print("  gets a DB record. Images 02–07 are uploaded to storage but not linked in DB.")
        print()
        _print_summary(result, dry_run=True, elapsed_s=time.monotonic() - t0)
        return

    # ---------------------------------------------------------------------------
    # Execute: upload + insert
    # ---------------------------------------------------------------------------
    if not supabase_url:
        print("[error] SUPABASE_URL is required for --execute.", file=sys.stderr)
        sys.exit(1)
    supabase = _build_client()

    for item in plan:
        rel = str(item.local_path.relative_to(CONTENT_ROOT))
        if rel not in available:
            continue

        print(f"  uploading {rel} …", end=" ", flush=True)
        ok, err = _upload_file(supabase, item)
        if not ok:
            print("FAILED")
            print(f"    reason: {err}", file=sys.stderr)
            result.failed.append((rel, err))
            continue

        pub_url = _public_url(supabase_url, item.storage_path)
        size_kb = round(item.local_path.stat().st_size / 1024)
        print(f"OK ({size_kb} KB)")
        result.uploaded.append(rel)

        if item.create_db_record:
            ok2, err2 = _insert_record(supabase, item, pub_url)
            if ok2:
                record_label = f"{item.title!r} media_type={item.media_type}"
                print(f"    [DB] inserted: {record_label}")
                result.inserted.append(record_label)
            else:
                print(f"    [DB] insert FAILED: {err2}", file=sys.stderr)
                result.failed.append((f"{rel} [DB insert]", err2))

    _print_summary(result, dry_run=False, elapsed_s=time.monotonic() - t0)


if __name__ == "__main__":
    main()

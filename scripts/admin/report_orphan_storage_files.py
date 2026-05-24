"""
report_orphan_storage_files.py

Report-only orphan detection for Supabase Storage.

Lists objects in the instaautopost-media bucket that are not referenced by
any ig_content_library row and are older than the grace period (default: 24h).

No files are deleted. This script is report-only.

Usage:
    SUPABASE_URL=... SUPABASE_SERVICE_ROLE_KEY=... \\
        python3 scripts/admin/report_orphan_storage_files.py [--grace-hours N]

An "orphan" is a Storage object whose path does not appear in the video_url
column of any ig_content_library row and that is older than the grace period.
Objects within the grace period are skipped to avoid flagging in-progress uploads.

Note: test-import carousel secondary images (uploaded by import_travel_test_batch.py
or similar scripts) may appear here as intentional unlinked objects.

Destructive cleanup is NOT implemented. Any deletion must be a future
explicit reviewed operation, run separately with careful pre-flight verification.
"""

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import unquote

try:
    from supabase import create_client
except ImportError:
    print("ERROR: supabase-py is required. Run: pip install supabase", file=sys.stderr)
    sys.exit(1)

BUCKET = "instaautopost-media"
DEFAULT_GRACE_HOURS = 24
STORAGE_PAGE_SIZE = 100
DB_PAGE_SIZE = 1000


def list_objects_recursive(storage, path: str = "") -> list:
    """Recursively list all file objects in the bucket under path, with pagination."""
    objects = []
    offset = 0
    while True:
        entries = (
            storage.from_(BUCKET).list(path, {"limit": STORAGE_PAGE_SIZE, "offset": offset})
            or []
        )
        for entry in entries:
            # Folders: no 'id' and no 'metadata'; files have at least one of these.
            is_folder = entry.get("id") is None and entry.get("metadata") is None
            full_path = f"{path}/{entry['name']}" if path else entry["name"]
            if is_folder:
                objects.extend(list_objects_recursive(storage, full_path))
            else:
                entry["_full_path"] = full_path
                objects.append(entry)
        if len(entries) < STORAGE_PAGE_SIZE:
            break
        offset += STORAGE_PAGE_SIZE
    return objects


def normalize_url_to_path(url: str, supabase_url: str, bucket: str) -> Optional[str]:
    """Extract the storage object path from a Supabase public storage URL."""
    prefix = f"{supabase_url.rstrip('/')}/storage/v1/object/public/{bucket}/"
    if url.startswith(prefix):
        return unquote(url[len(prefix):])
    return None


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Report orphan storage objects (report-only, no deletion).",
    )
    parser.add_argument(
        "--grace-hours",
        type=float,
        default=DEFAULT_GRACE_HOURS,
        help=f"Skip objects newer than this many hours (default: {DEFAULT_GRACE_HOURS}).",
    )
    args = parser.parse_args()

    supabase_url = os.environ.get("SUPABASE_URL")
    service_role_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not supabase_url or not service_role_key:
        print(
            "ERROR: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set.",
            file=sys.stderr,
        )
        sys.exit(1)

    client = create_client(supabase_url, service_role_key)

    print(f"Bucket: {BUCKET}")
    print(f"Grace period: {args.grace_hours}h (objects newer than this are skipped)")
    print()

    print("Listing storage objects...")
    all_objects = list_objects_recursive(client.storage)
    print(f"  {len(all_objects)} object(s) found in storage.")

    print("Fetching ig_content_library rows...")
    library_rows = []
    db_offset = 0
    while True:
        response = (
            client.table("ig_content_library")
            .select("id,title,video_url")
            .range(db_offset, db_offset + DB_PAGE_SIZE - 1)
            .execute()
        )
        batch = response.data or []
        library_rows.extend(batch)
        if len(batch) < DB_PAGE_SIZE:
            break
        db_offset += DB_PAGE_SIZE
    print(f"  {len(library_rows)} content library row(s) found.")
    print()

    referenced_paths: set = set()
    for row in library_rows:
        url = row.get("video_url") or ""
        path = normalize_url_to_path(url, supabase_url, BUCKET)
        if path:
            referenced_paths.add(path)

    cutoff = datetime.now(timezone.utc) - timedelta(hours=args.grace_hours)

    orphans = []
    skipped_grace = 0
    for obj in all_objects:
        full_path = obj.get("_full_path", "")
        if full_path in referenced_paths:
            continue

        created_at_str = obj.get("created_at") or obj.get("updated_at")
        age_unknown = False
        created_at: Optional[datetime] = None
        if created_at_str:
            try:
                created_at = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
            except ValueError:
                age_unknown = True
        else:
            age_unknown = True

        if not age_unknown and created_at is not None and created_at >= cutoff:
            skipped_grace += 1
            continue

        orphans.append(
            {
                "path": full_path,
                "created_at": created_at_str,
                "age_unknown": age_unknown,
            }
        )

    print("=" * 60)
    if skipped_grace:
        print(
            f"Skipped {skipped_grace} unreferenced object(s) within the {args.grace_hours}h grace period."
        )
        print()

    if orphans:
        print(f"ORPHAN OBJECTS: {len(orphans)} found")
        print()
        for o in orphans:
            age_note = "  [age unknown — treat as potential orphan]" if o["age_unknown"] else ""
            print(f"  {o['path']}")
            print(f"    created_at: {o['created_at']}{age_note}")
        print()
        print(
            "NOTE: test-import carousel secondary images (e.g. from import_travel_test_batch.py)"
        )
        print("      may appear above as intentional unlinked objects.")
    else:
        print(f"No orphan objects found older than {args.grace_hours}h.")

    print()
    print("No files deleted; report only.")
    print("=" * 60)
    print()
    print(
        "Cleanup deletion is not implemented. Any destructive cleanup must be a future"
    )
    print("explicit reviewed operation, run separately with careful pre-flight verification.")


if __name__ == "__main__":
    main()

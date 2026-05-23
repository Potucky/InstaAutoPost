"""
assign_content_to_schedule_slots.py

Assigns eligible content from ig_content_library to empty ig_schedule_slots.

Default: DRY RUN — prints a preview table and summary, writes nothing.
Pass --execute to apply updates to Supabase.

Does NOT:
  - publish to Instagram
  - create ig_publishing_queue rows
  - trigger GitHub Actions
  - upload files or modify Storage
  - enable cron
  - touch queue_id on any slot
"""

import argparse
import os
import random
import sys
from datetime import datetime

import httpx
from zoneinfo import ZoneInfo

TZ_NY = ZoneInfo("America/New_York")
TZ_UTC = ZoneInfo("UTC")

SCRIPT_NAME = "assign_content_to_schedule_slots.py"

# Titles (exact or prefix) that are always excluded as old/test content.
EXCLUDED_TITLE_PREFIXES = [
    "My first reels",
    "патп",
    "gjhlvj",
    "opkp",
    "1-1-1",
    "2-2-2",
]

DEFAULT_TITLE_PREFIXES = ["Reel", "Video Post", "Carousel"]
DEFAULT_SEED = 23


# ---------------------------------------------------------------------------
# Supabase helpers
# ---------------------------------------------------------------------------

def _headers(service_key: str) -> dict:
    return {
        "apikey": service_key,
        "Authorization": f"Bearer {service_key}",
        "Content-Type": "application/json",
    }


def fetch_eligible_content(base_url: str, service_key: str) -> list[dict]:
    """Fetch all content from ig_content_library with status draft or approved."""
    url = (
        f"{base_url}/rest/v1/ig_content_library"
        "?select=id,title,media_type,content_status,created_at"
        "&content_status=in.(draft,approved)"
        "&order=created_at.asc"
    )
    response = httpx.get(url, headers=_headers(service_key), timeout=30)
    response.raise_for_status()
    return response.json()


def fetch_empty_slots(base_url: str, service_key: str) -> list[dict]:
    """Fetch all empty slots ordered by scheduled_at ascending."""
    url = (
        f"{base_url}/rest/v1/ig_schedule_slots"
        "?select=id,slot_date,slot_window,scheduled_at,content_id,slot_status"
        "&slot_status=eq.empty"
        "&content_id=is.null"
        "&order=scheduled_at.asc"
    )
    response = httpx.get(url, headers=_headers(service_key), timeout=30)
    response.raise_for_status()
    return response.json()


def update_slot(base_url: str, service_key: str, slot_id: str, content_id: str) -> None:
    """Set content_id and slot_status='assigned' on a single slot row."""
    url = f"{base_url}/rest/v1/ig_schedule_slots?id=eq.{slot_id}"
    payload = {
        "content_id": content_id,
        "slot_status": "assigned",
        "notes": f"assigned by {SCRIPT_NAME}",
    }
    headers = {**_headers(service_key), "Prefer": "return=minimal"}
    response = httpx.patch(url, headers=headers, json=payload, timeout=30)
    response.raise_for_status()


# ---------------------------------------------------------------------------
# Filtering helpers
# ---------------------------------------------------------------------------

def is_excluded(title: str) -> bool:
    t = title.strip()
    for prefix in EXCLUDED_TITLE_PREFIXES:
        if t == prefix or t.startswith(prefix):
            return True
    return False


def matches_prefixes(title: str, prefixes: list[str]) -> bool:
    t = title.strip()
    return any(t.startswith(p) for p in prefixes)


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------

def fmt_ny(scheduled_at_str: str) -> str:
    dt = datetime.fromisoformat(scheduled_at_str).astimezone(TZ_NY)
    return dt.strftime("%Y-%m-%d %H:%M:%S %Z")


def print_preview(rows: list[tuple[dict, dict | None, str]]) -> None:
    """
    rows: list of (slot, content_or_None, action_str)
    """
    col = (12, 10, 25, 38, 10, 16, 14)
    header = (
        f"{'slot_date':<{col[0]}} "
        f"{'slot_window':<{col[1]}} "
        f"{'scheduled_at (NY)':<{col[2]}} "
        f"{'content_title':<{col[3]}} "
        f"{'media_type':<{col[4]}} "
        f"{'content_status':<{col[5]}} "
        f"{'action':<{col[6]}}"
    )
    sep = "-" * len(header)
    print(sep)
    print(header)
    print(sep)
    for slot, content, action in rows:
        ny = fmt_ny(slot["scheduled_at"])
        title = (content["title"] if content else "")[:37]
        mtype = (content["media_type"] if content else "")
        cstatus = (content["content_status"] if content else "")
        print(
            f"{slot['slot_date']:<{col[0]}} "
            f"{slot['slot_window']:<{col[1]}} "
            f"{ny:<{col[2]}} "
            f"{title:<{col[3]}} "
            f"{mtype:<{col[4]}} "
            f"{cstatus:<{col[5]}} "
            f"{action:<{col[6]}}"
        )
    print(sep)


def print_summary(
    total_fetched: int,
    excluded_count: int,
    prefix_filtered_count: int,
    already_assigned_in_db: int,
    eligible_count: int,
    empty_slots_count: int,
    pairs: list[tuple[dict, dict]],
    did_execute: bool,
) -> None:
    print()
    print("=== SUMMARY ===")
    print(f"  Content fetched (draft+approved)  : {total_fetched}")
    print(f"  Excluded old/test content         : {excluded_count}")
    print(f"  Filtered by title prefix          : {prefix_filtered_count}")
    print(f"  Already assigned in DB (skipped)  : {already_assigned_in_db}")
    print(f"  Eligible content                  : {eligible_count}")
    print(f"  Empty slots available             : {empty_slots_count}")
    assign_count = len(pairs)
    if did_execute:
        print(f"  Assigned                          : {assign_count}")
    else:
        print(f"  Would assign                      : {assign_count}")
    if pairs:
        first = min(s["scheduled_at"] for s, _ in pairs)
        last = max(s["scheduled_at"] for s, _ in pairs)
        first_ny = fmt_ny(first)
        last_ny = fmt_ny(last)
        print(f"  First assigned scheduled_at       : {first_ny}")
        print(f"  Last assigned scheduled_at        : {last_ny}")
    if not did_execute:
        print()
        print("  DRY RUN — no rows written. Pass --execute to apply.")
    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Assign eligible content to empty ig_schedule_slots. "
            "Default: dry run."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--title-prefixes",
        default=",".join(DEFAULT_TITLE_PREFIXES),
        help='Comma-separated title prefixes to include (default: "Reel,Video Post,Carousel")',
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of assignments to make (default: no limit)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=DEFAULT_SEED,
        help=f"RNG seed for --randomize-content (default: {DEFAULT_SEED})",
    )
    parser.add_argument(
        "--randomize-content",
        action="store_true",
        help="Randomize content assignment order (deterministic with --seed)",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Apply updates to Supabase (default: dry run)",
    )
    args = parser.parse_args()

    title_prefixes = [p.strip() for p in args.title_prefixes.split(",") if p.strip()]

    base_url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    service_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

    if not base_url or not service_key:
        print(
            "ERROR: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set.",
            file=sys.stderr,
        )
        sys.exit(1)

    # --- Fetch data ---
    print("Fetching content and slots from Supabase ...")
    try:
        all_content = fetch_eligible_content(base_url, service_key)
        empty_slots = fetch_empty_slots(base_url, service_key)
    except Exception as exc:
        print(f"ERROR: could not fetch data: {exc}", file=sys.stderr)
        sys.exit(1)

    total_fetched = len(all_content)
    print(f"  {total_fetched} draft/approved content records fetched.")
    print(f"  {len(empty_slots)} empty slots fetched.")
    print()

    # --- Filter content ---
    excluded: list[dict] = []
    prefix_filtered: list[dict] = []
    eligible: list[dict] = []

    for item in all_content:
        title = item.get("title", "")
        if is_excluded(title):
            excluded.append(item)
        elif not matches_prefixes(title, title_prefixes):
            prefix_filtered.append(item)
        else:
            eligible.append(item)

    # Detect content already assigned in DB (content_id already in a non-empty slot).
    # We count items in the eligible list whose id already appears as a content_id
    # in a slot that is NOT empty (meaning they were previously assigned elsewhere).
    # For this we need to fetch assigned slots' content_ids.
    already_assigned_ids: set[str] = set()
    try:
        url = (
            f"{base_url}/rest/v1/ig_schedule_slots"
            "?select=content_id"
            "&content_id=not.is.null"
        )
        resp = httpx.get(url, headers=_headers(service_key), timeout=30)
        resp.raise_for_status()
        for row in resp.json():
            if row.get("content_id"):
                already_assigned_ids.add(row["content_id"])
    except Exception as exc:
        print(
            f"WARNING: could not fetch assigned content_ids ({exc}). "
            "Skipping duplicate-assignment check.",
            file=sys.stderr,
        )

    already_in_db: list[dict] = []
    final_eligible: list[dict] = []
    for item in eligible:
        if item["id"] in already_assigned_ids:
            already_in_db.append(item)
        else:
            final_eligible.append(item)

    # --- Order / randomize content ---
    if args.randomize_content:
        rng = random.Random(args.seed)
        rng.shuffle(final_eligible)
    # else: already ordered by created_at ascending from the DB query

    # --- Pair content → slots ---
    limit = args.limit  # None means no limit
    pairs: list[tuple[dict, dict]] = []  # (slot, content)

    content_iter = iter(final_eligible)
    for slot in empty_slots:
        if limit is not None and len(pairs) >= limit:
            break
        content = next(content_iter, None)
        if content is None:
            break
        pairs.append((slot, content))

    # Build preview rows: assigned pairs first, then remaining empty slots (no action).
    assigned_slot_ids = {s["id"] for s, _ in pairs}
    content_map = {s["id"]: c for s, c in pairs}

    preview_rows: list[tuple[dict, dict | None, str]] = []
    for slot in empty_slots:
        if slot["id"] in assigned_slot_ids:
            action = "would assign" if not args.execute else "assign"
            preview_rows.append((slot, content_map[slot["id"]], action))
        else:
            preview_rows.append((slot, None, "skipped (no content)"))

    # --- Print preview ---
    print_preview(preview_rows)

    # --- Execute ---
    if args.execute and pairs:
        print(f"\nUpdating {len(pairs)} slots ...")
        errors = 0
        for slot, content in pairs:
            try:
                update_slot(base_url, service_key, slot["id"], content["id"])
            except Exception as exc:
                print(f"  ERROR updating slot {slot['id']}: {exc}", file=sys.stderr)
                errors += 1
        if errors:
            print(f"  {errors} update(s) failed.", file=sys.stderr)
        else:
            print("  All updates complete.")

    # --- Summary ---
    print_summary(
        total_fetched=total_fetched,
        excluded_count=len(excluded),
        prefix_filtered_count=len(prefix_filtered),
        already_assigned_in_db=len(already_in_db),
        eligible_count=len(final_eligible),
        empty_slots_count=len(empty_slots),
        pairs=pairs,
        did_execute=args.execute,
    )


if __name__ == "__main__":
    main()

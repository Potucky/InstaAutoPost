"""
generate_schedule_slots.py

Generates empty ig_schedule_slots rows for a date range.

Default: DRY RUN — prints a preview table and summary, inserts nothing.
Pass --execute to write rows to Supabase.

Does NOT:
  - publish to Instagram
  - trigger GitHub Actions
  - create ig_publishing_queue rows
  - assign content to slots
"""

import argparse
import hashlib
import os
import random
import sys
from datetime import date, datetime, timedelta

import httpx
from zoneinfo import ZoneInfo

TZ_NY = ZoneInfo("America/New_York")
TZ_UTC = ZoneInfo("UTC")

DEFAULT_WINDOWS = "morning=07:00:00-09:00:00,lunch=12:00:00-14:00:00,evening=18:00:00-20:00:00"
DEFAULT_END_DATE = "2026-07-01"
DEFAULT_SEED = 23


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

def parse_windows(windows_str: str) -> dict[str, tuple[tuple[int, int, int], tuple[int, int, int]]]:
    """Parse 'name=HH:MM:SS-HH:MM:SS,...' into {name: ((h,m,s),(h,m,s))}."""
    result = {}
    for part in windows_str.split(","):
        part = part.strip()
        name, times = part.split("=", 1)
        start_str, end_str = times.split("-", 1)
        result[name.strip()] = (
            tuple(int(x) for x in start_str.strip().split(":")),
            tuple(int(x) for x in end_str.strip().split(":")),
        )
    return result


def parse_date(s: str) -> date:
    return date.fromisoformat(s)


# ---------------------------------------------------------------------------
# Slot generation
# ---------------------------------------------------------------------------

def random_time_in_window(
    rng: random.Random,
    start: tuple[int, int, int],
    end: tuple[int, int, int],
) -> tuple[int, int, int]:
    """Return a random HH:MM:SS within [start, end) as a (h, m, s) tuple."""
    start_s = start[0] * 3600 + start[1] * 60 + start[2]
    end_s = end[0] * 3600 + end[1] * 60 + end[2]
    total_s = rng.randint(start_s, end_s - 1)
    h, remainder = divmod(total_s, 3600)
    m, s = divmod(remainder, 60)
    return (h, m, s)


def generate_slots(
    start: date,
    end: date,
    windows: dict,
    seed: int,
) -> list[dict]:
    """
    Generate one slot per window per day from start up to (not including) end.

    Uniqueness of HH:MM:SS across the entire schedule is enforced by
    regenerating with a new offset until no collision occurs.
    Each day-window pair gets a deterministic seed derived from the global
    seed, the date, and the window name so results are stable across runs.
    """
    rng = random.Random(seed)

    # Window order determines iteration — preserve insertion order.
    window_names = list(windows.keys())

    slots: list[dict] = []
    used_times: set[tuple[int, int, int]] = set()  # global HH:MM:SS uniqueness

    current = start
    while current < end:
        for window_name in window_names:
            w_start, w_end = windows[window_name]

            # Deterministic per (date, window) using SHA-256 derived seed.
            # Python's hash() is randomized by PYTHONHASHSEED — use SHA-256 for stability.
            _hash_input = f"{seed}:{current.isoformat()}:{window_name}".encode()
            local_seed = int(hashlib.sha256(_hash_input).hexdigest(), 16) & 0xFFFFFFFF
            local_rng = random.Random(local_seed)

            # Try up to 3600 offsets to find a unique second.
            found = False
            for _ in range(3600):
                hms = random_time_in_window(local_rng, w_start, w_end)
                if hms not in used_times:
                    used_times.add(hms)
                    found = True
                    break

            if not found:
                print(
                    f"WARNING: could not find a unique second for {current} {window_name} — skipping.",
                    file=sys.stderr,
                )
                continue

            h, m, s = hms
            # Build timestamptz in New York local time, then convert to UTC.
            ny_dt = datetime(current.year, current.month, current.day, h, m, s, tzinfo=TZ_NY)
            utc_dt = ny_dt.astimezone(TZ_UTC)

            slots.append(
                {
                    "slot_date": current.isoformat(),
                    "slot_window": window_name,
                    "scheduled_at": utc_dt.isoformat(),
                    "scheduled_at_ny": ny_dt,
                    "scheduled_at_utc": utc_dt,
                }
            )

        current += timedelta(days=1)

    return slots


# ---------------------------------------------------------------------------
# Supabase helpers
# ---------------------------------------------------------------------------

def get_existing_scheduled_ats(base_url: str, service_key: str) -> set[str]:
    """Fetch all scheduled_at values already in ig_schedule_slots."""
    headers = {
        "apikey": service_key,
        "Authorization": f"Bearer {service_key}",
    }
    url = f"{base_url}/rest/v1/ig_schedule_slots?select=scheduled_at"
    response = httpx.get(url, headers=headers, timeout=30)
    response.raise_for_status()
    return {row["scheduled_at"] for row in response.json()}


def insert_slots(base_url: str, service_key: str, rows: list[dict]) -> None:
    """Bulk-insert slot rows into ig_schedule_slots."""
    headers = {
        "apikey": service_key,
        "Authorization": f"Bearer {service_key}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }
    url = f"{base_url}/rest/v1/ig_schedule_slots"
    response = httpx.post(url, headers=headers, json=rows, timeout=60)
    response.raise_for_status()


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------

def print_preview(slots_with_action: list[tuple[dict, str]]) -> None:
    col_widths = (12, 10, 27, 27, 22)
    header = (
        f"{'slot_date':<{col_widths[0]}} "
        f"{'slot_window':<{col_widths[1]}} "
        f"{'scheduled_at (NY)':<{col_widths[2]}} "
        f"{'scheduled_at (UTC)':<{col_widths[3]}} "
        f"{'action':<{col_widths[4]}}"
    )
    separator = "-" * len(header)
    print(separator)
    print(header)
    print(separator)
    for slot, action in slots_with_action:
        ny_str = slot["scheduled_at_ny"].strftime("%Y-%m-%d %H:%M:%S %Z")
        utc_str = slot["scheduled_at_utc"].strftime("%Y-%m-%d %H:%M:%S %Z")
        print(
            f"{slot['slot_date']:<{col_widths[0]}} "
            f"{slot['slot_window']:<{col_widths[1]}} "
            f"{ny_str:<{col_widths[2]}} "
            f"{utc_str:<{col_widths[3]}} "
            f"{action:<{col_widths[4]}}"
        )
    print(separator)


def print_summary(
    total_generated: int,
    skipped: int,
    to_insert: int,
    did_execute: bool,
    slots_to_insert: list[dict],
    all_hms_unique: bool,
) -> None:
    print()
    print("=== SUMMARY ===")
    print(f"  Generated slots       : {total_generated}")
    print(f"  Duplicate slots skipped: {skipped}")
    if did_execute:
        print(f"  Inserted              : {to_insert}")
    else:
        print(f"  Would insert          : {to_insert}")
    if slots_to_insert:
        first = min(s["scheduled_at_utc"] for s in slots_to_insert)
        last = max(s["scheduled_at_utc"] for s in slots_to_insert)
        print(f"  First scheduled time  : {first.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        print(f"  Last scheduled time   : {last.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    print(f"  All HH:MM:SS unique   : {'yes' if all_hms_unique else 'NO — COLLISION DETECTED'}")
    if not did_execute:
        print()
        print("  DRY RUN — no rows written. Pass --execute to insert.")
    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate empty ig_schedule_slots rows. Default: dry run.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--start-date", default=None, help="Start date YYYY-MM-DD (default: today)")
    parser.add_argument("--end-date", default=DEFAULT_END_DATE, help="Exclusive end date YYYY-MM-DD")
    parser.add_argument("--windows", default=DEFAULT_WINDOWS, help="Window definitions")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help="RNG seed for deterministic output")
    parser.add_argument("--execute", action="store_true", help="Insert rows into Supabase (default: dry run)")
    args = parser.parse_args()

    today = date.today()
    start = parse_date(args.start_date) if args.start_date else today
    end = parse_date(args.end_date)

    if start >= end:
        print(f"ERROR: start-date {start} must be before end-date {end}.", file=sys.stderr)
        sys.exit(1)

    windows = parse_windows(args.windows)

    base_url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    service_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

    if args.execute and (not base_url or not service_key):
        print("ERROR: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set for --execute.", file=sys.stderr)
        sys.exit(1)

    # --- Generate slots (randomness happens only here) ---
    print(f"Generating slots: {start} to {end} (exclusive), seed={args.seed}")
    print(f"Windows: {', '.join(f'{k}={v[0][0]:02d}:{v[0][1]:02d}:{v[0][2]:02d}-{v[1][0]:02d}:{v[1][1]:02d}:{v[1][2]:02d}' for k, v in windows.items())}")
    print()

    slots = generate_slots(start, end, windows, args.seed)
    total_generated = len(slots)

    # Verify global HH:MM:SS uniqueness.
    all_hms = [s["scheduled_at_ny"].strftime("%H:%M:%S") for s in slots]
    all_hms_unique = len(all_hms) == len(set(all_hms))

    # --- Check for duplicates already in DB ---
    existing: set[str] = set()
    if args.execute or base_url:
        try:
            existing = get_existing_scheduled_ats(base_url, service_key)
        except Exception as exc:
            if args.execute:
                print(f"ERROR: could not fetch existing slots: {exc}", file=sys.stderr)
                sys.exit(1)
            # Dry run without DB access — treat all as new.
            print(f"WARNING: could not reach Supabase to check duplicates ({exc}). Assuming no existing slots.", file=sys.stderr)

    # Normalise existing timestamps to comparable format.
    def normalise(ts: str) -> str:
        return datetime.fromisoformat(ts).astimezone(TZ_UTC).isoformat()

    existing_norm = {normalise(ts) for ts in existing}

    slots_to_insert: list[dict] = []
    skipped = 0
    slots_with_action: list[tuple[dict, str]] = []

    for slot in slots:
        slot_utc_iso = slot["scheduled_at_utc"].isoformat()
        if slot_utc_iso in existing_norm:
            slots_with_action.append((slot, "skipped duplicate"))
            skipped += 1
        else:
            action = "would insert" if not args.execute else "insert"
            slots_with_action.append((slot, action))
            slots_to_insert.append(slot)

    # --- Print preview ---
    print_preview(slots_with_action)

    # --- Execute insert ---
    if args.execute and slots_to_insert:
        db_rows = [
            {
                "slot_date": s["slot_date"],
                "slot_window": s["slot_window"],
                "scheduled_at": s["scheduled_at"],
                "slot_status": "empty",
            }
            for s in slots_to_insert
        ]
        print(f"\nInserting {len(db_rows)} rows into ig_schedule_slots ...")
        try:
            insert_slots(base_url, service_key, db_rows)
            print("Insert complete.")
        except Exception as exc:
            print(f"ERROR: insert failed: {exc}", file=sys.stderr)
            sys.exit(1)

    # --- Summary ---
    print_summary(
        total_generated=total_generated,
        skipped=skipped,
        to_insert=len(slots_to_insert),
        did_execute=args.execute,
        slots_to_insert=slots_to_insert,
        all_hms_unique=all_hms_unique,
    )


if __name__ == "__main__":
    main()

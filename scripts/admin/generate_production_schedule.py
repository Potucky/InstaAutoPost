"""
generate_production_schedule.py

Generates and previews a production posting schedule across a date range.

Default: DRY RUN — prints a preview table, writes nothing to the database.
Pass --execute to apply (v1: preview only — DB writes not yet implemented).

Does NOT:
  - publish to Instagram
  - create ig_publishing_queue rows
  - create ig_schedule_slots rows (v1: preview only)
  - trigger GitHub Actions
  - upload files or modify Storage
"""

import argparse
import hashlib
import itertools
import random
import sys
from datetime import date, datetime, timedelta

from zoneinfo import ZoneInfo

TZ_NY = ZoneInfo("America/New_York")
TZ_UTC = ZoneInfo("UTC")

DEFAULT_END_DATE = "2026-07-01"
DEFAULT_SEED = 23

CONTENT_TYPES = ["REEL", "VIDEO", "CAROUSEL"]

# Three daily windows in America/New_York. Each value is ((h,m,s), (h,m,s)).
WINDOWS: dict[str, tuple[tuple[int, int, int], tuple[int, int, int]]] = {
    "morning": ((7, 0, 0), (9, 0, 0)),
    "lunch": ((12, 0, 0), (14, 0, 0)),
    "evening": ((18, 0, 0), (20, 0, 0)),
}


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

def parse_date(s: str) -> date:
    return date.fromisoformat(s)


# ---------------------------------------------------------------------------
# Content-type rotation
# ---------------------------------------------------------------------------

def build_type_rotation(seed: int) -> list[list[str]]:
    """
    Return a shuffled list of all 6 permutations of CONTENT_TYPES.

    Cycling through this list guarantees:
    - Every day's windows are each assigned a distinct content type.
    - No two consecutive days (including across the 6-day cycle boundary)
      share the same per-window ordering, because all 6 permutations are
      distinct and the cycle never places the same permutation adjacent to
      itself.
    """
    perms = [list(p) for p in itertools.permutations(CONTENT_TYPES)]
    rng = random.Random(seed)
    rng.shuffle(perms)
    return perms


# ---------------------------------------------------------------------------
# Slot generation
# ---------------------------------------------------------------------------

def random_time_in_window(
    rng: random.Random,
    start: tuple[int, int, int],
    end: tuple[int, int, int],
) -> tuple[int, int, int]:
    """Return a random HH:MM:SS within [start, end) as an (h, m, s) tuple."""
    start_s = start[0] * 3600 + start[1] * 60 + start[2]
    end_s = end[0] * 3600 + end[1] * 60 + end[2]
    total_s = rng.randint(start_s, end_s - 1)
    h, remainder = divmod(total_s, 3600)
    m, s = divmod(remainder, 60)
    return (h, m, s)


def generate_schedule(
    start: date,
    end: date,
    seed: int,
) -> list[dict]:
    """
    Generate one planned slot per window per day from start up to (not including) end.

    Jitter: random time within each window, derived from a per-(date, window)
    seed so output is stable across repeated runs with the same seed.

    Uniqueness: global HH:MM:SS uniqueness enforced across the full schedule.
    Each (date, window) retries up to 3 600 times to find a unique second.

    Content-type rotation: cycles through all 6 permutations of CONTENT_TYPES
    one permutation per day. The windows for that day are assigned the
    types in permutation order (morning → [0], lunch → [1], evening → [2]).
    No two consecutive days share the same daily ordering.
    """
    window_names = list(WINDOWS.keys())
    type_rotation = build_type_rotation(seed)
    rotation_cycle = itertools.cycle(type_rotation)

    used_times: set[tuple[int, int, int]] = set()
    slots: list[dict] = []

    current = start
    while current < end:
        day_types = next(rotation_cycle)

        for i, window_name in enumerate(window_names):
            w_start, w_end = WINDOWS[window_name]
            media_type = day_types[i]

            digest = hashlib.sha256(f"{seed}:{current.isoformat()}:{window_name}".encode()).digest()
            local_seed = int.from_bytes(digest[:4], "big")
            local_rng = random.Random(local_seed)

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
            ny_dt = datetime(current.year, current.month, current.day, h, m, s, tzinfo=TZ_NY)
            utc_dt = ny_dt.astimezone(TZ_UTC)

            slots.append(
                {
                    "slot_date": current.isoformat(),
                    "slot_window": window_name,
                    "media_type": media_type,
                    "scheduled_at_ny": ny_dt,
                    "scheduled_at_utc": utc_dt,
                }
            )

        current += timedelta(days=1)

    return slots


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------

def print_preview(slots: list[dict]) -> None:
    col = (12, 10, 25, 25, 10)
    header = (
        f"{'date':<{col[0]}} "
        f"{'window':<{col[1]}} "
        f"{'scheduled ET':<{col[2]}} "
        f"{'scheduled UTC':<{col[3]}} "
        f"{'media_type':<{col[4]}}"
    )
    sep = "-" * len(header)
    print(sep)
    print(header)
    print(sep)
    for slot in slots:
        ny_str = slot["scheduled_at_ny"].strftime("%Y-%m-%d %H:%M:%S %Z")
        utc_str = slot["scheduled_at_utc"].strftime("%Y-%m-%d %H:%M:%S %Z")
        print(
            f"{slot['slot_date']:<{col[0]}} "
            f"{slot['slot_window']:<{col[1]}} "
            f"{ny_str:<{col[2]}} "
            f"{utc_str:<{col[3]}} "
            f"{slot['media_type']:<{col[4]}}"
        )
    print(sep)


def print_summary(slots: list[dict], did_execute: bool) -> None:
    total = len(slots)
    all_hms = [s["scheduled_at_ny"].strftime("%H:%M:%S") for s in slots]
    all_utc = [s["scheduled_at_utc"].isoformat() for s in slots]
    hms_unique = len(all_hms) == len(set(all_hms))
    utc_unique = len(all_utc) == len(set(all_utc))

    print()
    print("=== SUMMARY ===")
    print(f"  Total slots planned          : {total}")
    if slots:
        first = min(s["scheduled_at_utc"] for s in slots)
        last = max(s["scheduled_at_utc"] for s in slots)
        print(f"  First scheduled_at (UTC)     : {first.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        print(f"  Last scheduled_at (UTC)      : {last.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    print(f"  All HH:MM:SS unique (ET)     : {'yes' if hms_unique else 'NO — COLLISION DETECTED'}")
    print(f"  All scheduled_at unique (UTC): {'yes' if utc_unique else 'NO — COLLISION DETECTED'}")
    for mtype in CONTENT_TYPES:
        count = sum(1 for s in slots if s["media_type"] == mtype)
        print(f"  {mtype:<30}: {count}")

    print()
    if did_execute:
        print("  NOTE: --execute passed, but v1 is preview only — no rows written.")
        print("  DB write support will be added in a future version.")
    else:
        print("  DRY RUN — no rows written. Pass --execute to apply (v1: preview only).")
    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Preview a production posting schedule across a date range. "
            "Default: dry run — prints table, writes nothing."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--start-date",
        default=None,
        help="Start date YYYY-MM-DD (default: today)",
    )
    parser.add_argument(
        "--end-date",
        default=DEFAULT_END_DATE,
        help=f"Exclusive end date YYYY-MM-DD (default: {DEFAULT_END_DATE})",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=DEFAULT_SEED,
        help=f"RNG seed for deterministic output (default: {DEFAULT_SEED})",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Apply to database (v1: preview only — no DB writes yet)",
    )
    args = parser.parse_args()

    today = date.today()
    start = parse_date(args.start_date) if args.start_date else today
    end = parse_date(args.end_date)

    if start >= end:
        print(f"ERROR: start-date {start} must be before end-date {end}.", file=sys.stderr)
        sys.exit(1)

    print("=" * 64)
    print("  generate_production_schedule.py")
    print("  DRY RUN — this script does not write to the database.")
    print("  It does not publish to Instagram.")
    print("  It does not create ig_publishing_queue rows.")
    print("  It does not create ig_schedule_slots rows.")
    print("=" * 64)
    print()
    print(f"  Period  : {start} to {end} (exclusive)")
    print(f"  Windows : morning 07:00-09:00 ET | lunch 12:00-14:00 ET | evening 18:00-20:00 ET")
    print(f"  Types   : {', '.join(CONTENT_TYPES)} (rotating permutation, no consecutive repeat)")
    print(f"  Seed    : {args.seed}")
    print()

    slots = generate_schedule(start, end, args.seed)

    print_preview(slots)
    print_summary(slots, did_execute=args.execute)


if __name__ == "__main__":
    main()

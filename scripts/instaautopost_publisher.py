#!/usr/bin/env python3
"""
InstaAutoPost Publisher Worker
Processes exactly one due queue item per execution.

Dry-run by default. Set INSTAGRAM_API_ENABLED=true to publish live.
"""

import os
import re
import sys
import uuid
import time
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

import requests
from supabase import create_client, Client

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
WORKER_VERSION = "1.2.0"
WORKER_ID = f"worker-{uuid.uuid4().hex[:8]}"
DRY_RUN = os.environ.get("INSTAGRAM_API_ENABLED", "false").strip().lower() != "true"

IG_API_BASE = "https://graph.facebook.com/v19.0"
CONTAINER_POLL_INTERVAL_S = 5
CONTAINER_POLL_MAX_ATTEMPTS = 12  # 60 seconds total

RETRY_BACKOFF_MINUTES = {1: 5, 2: 10, 3: 20}

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%SZ",
    stream=sys.stdout,
)
log = logging.getLogger("instaautopost")


# ---------------------------------------------------------------------------
# Supabase client
# ---------------------------------------------------------------------------
def get_supabase() -> Client:
    url = os.environ.get("SUPABASE_URL", "").strip()
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    if not url or not key:
        log.error("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required")
        sys.exit(1)
    return create_client(url, key)


# ---------------------------------------------------------------------------
# Queue operations
# ---------------------------------------------------------------------------
def claim_queue_item(supabase: Client) -> Optional[dict]:
    """Atomically claim one due queue item using the DB-side locking function."""
    result = supabase.rpc("claim_next_queue_item", {"p_worker_id": WORKER_ID}).execute()
    if result.data:
        return result.data[0]
    return None


def get_content(supabase: Client, content_id: str) -> dict:
    result = (
        supabase.table("ig_content_library")
        .select("*")
        .eq("id", content_id)
        .single()
        .execute()
    )
    if not result.data:
        raise ValueError(f"Content {content_id} not found in ig_content_library")
    return result.data


def mark_published(supabase: Client, queue_id: str, media_id: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    supabase.table("ig_publishing_queue").update({
        "queue_status": "published",
        "published_at": now,
        "external_media_id": media_id,
        "locked_at": None,
        "locked_by": None,
        "failure_reason": None,
    }).eq("id", queue_id).execute()


def mark_failed_or_retry(
    supabase: Client,
    queue_id: str,
    error: str,
    attempt_count: int,
    max_attempts: int,
) -> None:
    if attempt_count < max_attempts:
        backoff = RETRY_BACKOFF_MINUTES.get(attempt_count, 20)
        next_retry = datetime.now(timezone.utc) + timedelta(minutes=backoff)
        supabase.table("ig_publishing_queue").update({
            "queue_status": "retry_scheduled",
            "next_retry_at": next_retry.isoformat(),
            "failure_reason": error[:2000],
            "locked_at": None,
            "locked_by": None,
        }).eq("id", queue_id).execute()
        log.warning(f"Retry scheduled at {next_retry.isoformat()} (backoff={backoff}m)")
    else:
        supabase.table("ig_publishing_queue").update({
            "queue_status": "failed",
            "failure_reason": error[:2000],
            "locked_at": None,
            "locked_by": None,
        }).eq("id", queue_id).execute()
        log.error("Max attempts reached — queue item marked as failed")


def write_attempt(
    supabase: Client,
    queue_id: str,
    attempt_number: int,
    status: str,
    duration_ms: int,
    container_id: Optional[str] = None,
    media_id: Optional[str] = None,
    error_message: Optional[str] = None,
    response_data: Optional[dict] = None,
) -> None:
    supabase.table("ig_publish_attempts").insert({
        "queue_id": queue_id,
        "attempt_number": attempt_number,
        "status": status,
        "container_id": container_id,
        "media_id": media_id,
        "error_message": error_message[:2000] if error_message else None,
        "response_data": response_data,
        "duration_ms": duration_ms,
        "dry_run": DRY_RUN,
        "worker_version": WORKER_VERSION,
    }).execute()


def _anchor_media_id(
    supabase: Client,
    queue_id: str,
    media_id: str,
    access_token: str,
) -> None:
    """Persist external_media_id immediately after Instagram confirms publication.

    claim_next_queue_item filters WHERE external_media_id IS NULL, so once this
    write succeeds no future worker run can reclaim and re-publish this row —
    even if all subsequent DB writes (write_attempt, mark_published) fail.

    If this write fails: attempt a fallback to queue_status='failed' (also blocks
    reclaim via the status filter), log CRITICAL, and exit. Never return to the
    caller when the anchor cannot be established.
    """
    now = datetime.now(timezone.utc).isoformat()
    try:
        # Set external_media_id AND published_at together to satisfy the
        # chk_published_proof constraint (both must be null or both non-null).
        # queue_status='published' and cleared lock fields make the row terminal
        # so no future worker run can reclaim it even if mark_published() fails.
        supabase.table("ig_publishing_queue").update({
            "external_media_id": media_id,
            "published_at": now,
            "queue_status": "published",
            "failure_reason": None,
            "locked_at": None,
            "locked_by": None,
            "worker_metadata": {
                "post_publish_reconciliation": True,
                "media_id_anchored_at": now,
                "status": "published_state_anchored",
            },
            "updated_at": now,
        }).eq("id", queue_id).execute()
        log.info(
            f"Anchored external_media_id={media_id} published_at={now} on queue_id={queue_id} "
            f"— row is terminal, duplicate publish protection active"
        )
    except Exception as anchor_exc:
        error_str = _redact(str(anchor_exc), access_token)
        log.critical(
            f"ANCHOR_MEDIA_ID_FAILED | queue_id={queue_id} | media_id={media_id} "
            f"| external_media_id NOT saved — duplicate publish risk active | {error_str}"
        )
        # Fallback: queue_status='failed' excludes the row from claim_next_queue_item
        # (eligible set is 'ready','scheduled','retry_scheduled','processing' only).
        try:
            supabase.table("ig_publishing_queue").update({
                "queue_status": "failed",
                "failure_reason": (
                    f"POST_PUBLISH_DB_ERROR: media published as {media_id} "
                    f"but external_media_id save failed — manual reconciliation required"
                )[:2000],
                "locked_at": None,
                "locked_by": None,
                "updated_at": now,
            }).eq("id", queue_id).execute()
            log.critical(
                f"Fallback: queue_id={queue_id} marked failed to block reclaim. "
                f"OPERATOR: set external_media_id={media_id} and queue_status=published manually."
            )
        except Exception:
            log.critical(
                f"ANCHOR_AND_FALLBACK_BOTH_FAILED | queue_id={queue_id} | media_id={media_id} "
                f"| Row may be reclaimed and re-published after lock expires. "
                f"IMMEDIATE OPERATOR ACTION REQUIRED."
            )
        sys.exit(1)


# ---------------------------------------------------------------------------
# Security helpers
# ---------------------------------------------------------------------------
def _redact(text: str, *secrets: str) -> str:
    """Remove sensitive values from a string before logging or storing."""
    result = str(text)
    for secret in secrets:
        if secret:
            result = result.replace(secret, "[REDACTED]")
    # Catch any remaining access_token= query-param values (e.g. in URLs)
    result = re.sub(r"(access_token=)[^&\s\"']+", r"\1[REDACTED]", result)
    # Catch Bearer tokens
    result = re.sub(r"(Bearer\s+)\S+", r"\1[REDACTED]", result, flags=re.IGNORECASE)
    return result


def _redact_url(url: str) -> str:
    """Strip query string from a URL before logging — signed URLs embed secrets in params."""
    if "?" in url:
        return url.split("?")[0] + "?[PARAMS_REDACTED]"
    return url


def _safe_raise(resp: "requests.Response", context: str = "IG API") -> None:
    """Raise a RuntimeError with only the HTTP status — never the full request URL."""
    if not resp.ok:
        raise RuntimeError(f"{context} error: HTTP {resp.status_code} {resp.reason}")


# ---------------------------------------------------------------------------
# Instagram Graph API
# ---------------------------------------------------------------------------
def ig_create_container(
    ig_user_id: str,
    access_token: str,
    video_url: str,
    caption: str,
) -> str:
    """Create a Reels media container. Returns container_id."""
    url = f"{IG_API_BASE}/{ig_user_id}/media"
    payload = {
        "video_url": video_url,
        "caption": caption,
        "media_type": "REELS",
        "access_token": access_token,
    }
    resp = requests.post(url, data=payload, timeout=30)
    _safe_raise(resp, "IG container creation")
    data = resp.json()
    if "error" in data:
        raise RuntimeError(f"IG container creation error: HTTP {resp.status_code} code={data['error'].get('code')} type={data['error'].get('type')}")
    container_id = data.get("id")
    if not container_id:
        raise RuntimeError("IG container creation: no container id in response")
    log.info(f"Created container: {container_id}")
    return container_id


def ig_poll_container(container_id: str, access_token: str) -> str:
    """Poll container status until FINISHED or ERROR. Returns final status_code."""
    url = f"{IG_API_BASE}/{container_id}"
    for attempt in range(1, CONTAINER_POLL_MAX_ATTEMPTS + 1):
        resp = requests.get(
            url,
            params={"fields": "status_code,status", "access_token": access_token},
            timeout=30,
        )
        _safe_raise(resp, "IG container poll")
        data = resp.json()
        status_code = data.get("status_code", "UNKNOWN")
        log.info(f"Container poll {attempt}/{CONTAINER_POLL_MAX_ATTEMPTS}: {status_code}")
        if status_code == "FINISHED":
            return status_code
        if status_code == "ERROR":
            raise RuntimeError(f"Container entered ERROR state: status_code={status_code}")
        time.sleep(CONTAINER_POLL_INTERVAL_S)
    raise RuntimeError(
        f"Container not ready after {CONTAINER_POLL_MAX_ATTEMPTS} polls "
        f"({CONTAINER_POLL_MAX_ATTEMPTS * CONTAINER_POLL_INTERVAL_S}s)"
    )


def ig_publish(ig_user_id: str, access_token: str, container_id: str) -> str:
    """Publish a finished container. Returns media_id."""
    url = f"{IG_API_BASE}/{ig_user_id}/media_publish"
    payload = {
        "creation_id": container_id,
        "access_token": access_token,
    }
    resp = requests.post(url, data=payload, timeout=30)
    _safe_raise(resp, "IG publish")
    data = resp.json()
    if "error" in data:
        raise RuntimeError(f"IG publish error: HTTP {resp.status_code} code={data['error'].get('code')} type={data['error'].get('type')}")
    media_id = data.get("id")
    if not media_id:
        raise RuntimeError("IG publish: no media id in response")
    log.info(f"Published media: {media_id}")
    return media_id


# ---------------------------------------------------------------------------
# Processing logic
# ---------------------------------------------------------------------------
def process_item(supabase: Client, item: dict, content: dict) -> None:
    queue_id = item["id"]
    attempt_number = item["attempt_count"]  # already incremented by claim function
    max_attempts = item["max_attempts"]
    start_time = time.monotonic()

    log.info(
        f"Processing queue item {queue_id} | "
        f"attempt={attempt_number}/{max_attempts} | "
        f"dry_run={DRY_RUN}"
    )

    # Guard: never republish
    if item.get("published_at") or item.get("external_media_id"):
        log.warning(f"Item {queue_id} already published — skipping")
        return

    if DRY_RUN:
        _process_dry_run(supabase, item, content, attempt_number, start_time)
    else:
        _process_live(supabase, item, content, attempt_number, start_time)


def _process_dry_run(
    supabase: Client,
    item: dict,
    content: dict,
    attempt_number: int,
    start_time: float,
) -> None:
    queue_id = item["id"]
    safe_url = _redact_url(content["video_url"])
    log.info(f"[DRY RUN] Would publish: '{content['title']}' | url={safe_url}")
    log.info("[DRY RUN] Instagram API not called")

    duration_ms = int((time.monotonic() - start_time) * 1000)
    write_attempt(
        supabase,
        queue_id=queue_id,
        attempt_number=attempt_number,
        status="dry_run",
        duration_ms=duration_ms,
        response_data={"dry_run": True, "content_id": content["id"]},
    )

    # In dry-run: reset to scheduled so item remains in queue for real run
    supabase.table("ig_publishing_queue").update({
        "queue_status": "scheduled",
        "attempt_count": attempt_number - 1,  # un-increment so real run counts from same baseline
        "locked_at": None,
        "locked_by": None,
        "failure_reason": None,
    }).eq("id", queue_id).execute()

    log.info("[DRY RUN] Item reset to 'scheduled' — no state permanently changed")


def _process_live(
    supabase: Client,
    item: dict,
    content: dict,
    attempt_number: int,
    start_time: float,
) -> None:
    queue_id = item["id"]
    max_attempts = item["max_attempts"]

    # Env vars are validated in main() before claiming, but read here for use.
    ig_user_id = os.environ.get("IG_USER_ID", "").strip()
    access_token = os.environ.get("IG_ACCESS_TOKEN", "").strip()

    caption = content.get("caption") or ""
    hashtags = content.get("hashtags") or []
    if hashtags:
        caption = caption.rstrip() + "\n\n" + " ".join(hashtags)

    container_id: Optional[str] = None
    media_id: Optional[str] = None

    # Phase 1: pre-publish (container creation + polling + publish call).
    # No media_id yet — failures here are safe to retry.
    try:
        container_id = ig_create_container(
            ig_user_id=ig_user_id,
            access_token=access_token,
            video_url=content["video_url"],
            caption=caption,
        )
        ig_poll_container(container_id=container_id, access_token=access_token)
        media_id = ig_publish(
            ig_user_id=ig_user_id,
            access_token=access_token,
            container_id=container_id,
        )
    except Exception as exc:
        duration_ms = int((time.monotonic() - start_time) * 1000)
        error_str = _redact(str(exc), access_token)
        log.error(f"Publish failed (pre-media_id): {error_str}")
        write_attempt(
            supabase,
            queue_id=queue_id,
            attempt_number=attempt_number,
            status="failed",
            duration_ms=duration_ms,
            container_id=container_id,
            error_message=error_str,
        )
        mark_failed_or_retry(
            supabase,
            queue_id=queue_id,
            error=error_str,
            attempt_count=attempt_number,
            max_attempts=max_attempts,
        )
        sys.exit(1)

    # Immediately anchor external_media_id before any other DB writes.
    # claim_next_queue_item filters WHERE external_media_id IS NULL, so once
    # this succeeds the row can never be reclaimed and re-published — even if
    # write_attempt() or mark_published() fail afterward.
    # _anchor_media_id() exits the process if the anchor cannot be established.
    _anchor_media_id(supabase, queue_id=queue_id, media_id=media_id, access_token=access_token)

    # Phase 2: post-publish DB writes.
    # Instagram has confirmed the publish and external_media_id is anchored.
    # Any failure here must NOT trigger a retry — duplicate publish is already
    # prevented by the anchored external_media_id. An operator reconciles the
    # remaining DB state (published_at, queue_status) using the media_id in logs.
    duration_ms = int((time.monotonic() - start_time) * 1000)
    try:
        write_attempt(
            supabase,
            queue_id=queue_id,
            attempt_number=attempt_number,
            status="success",
            duration_ms=duration_ms,
            container_id=container_id,
            media_id=media_id,
            response_data={"container_id": container_id, "media_id": media_id},
        )
        mark_published(supabase, queue_id=queue_id, media_id=media_id)
        log.info(f"Published successfully: media_id={media_id}")
    except Exception as exc:
        # CRITICAL: Instagram published the media but write_attempt or mark_published failed.
        # external_media_id is already anchored — this row cannot be reclaimed or re-published.
        # Operator must set published_at and queue_status=published manually.
        error_str = _redact(str(exc), access_token)
        log.critical(
            f"POST-PUBLISH DB FAILURE | queue_id={queue_id} "
            f"| media_id={media_id} | container_id={container_id} "
            f"| external_media_id anchored — no duplicate publish risk "
            f"| MANUAL RECONCILIATION REQUIRED | {error_str}"
        )
        # Best-effort: update queue_status to failed with reconciliation note.
        # external_media_id is already set so the row is protected regardless.
        try:
            supabase.table("ig_publishing_queue").update({
                "queue_status": "failed",
                "failure_reason": (
                    f"POST_PUBLISH_DB_ERROR: media published as {media_id} "
                    f"but final DB update failed — manual reconciliation required"
                )[:2000],
                "locked_at": None,
                "locked_by": None,
            }).eq("id", queue_id).execute()
        except Exception:
            pass
        sys.exit(1)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main() -> None:
    log.info(f"InstaAutoPost Publisher Worker {WORKER_VERSION} | id={WORKER_ID} | dry_run={DRY_RUN}")

    supabase = get_supabase()

    # Validate live-only env vars BEFORE claiming a queue row.
    # A misconfigured worker must exit here, not after locking a row.
    if not DRY_RUN:
        ig_user_id = os.environ.get("IG_USER_ID", "").strip()
        access_token = os.environ.get("IG_ACCESS_TOKEN", "").strip()
        if not ig_user_id or not access_token:
            log.error(
                "IG_USER_ID and IG_ACCESS_TOKEN are required for live mode "
                "— exiting without claiming a queue row"
            )
            sys.exit(1)

    item = claim_queue_item(supabase)
    if item is None:
        log.info("No due queue items — nothing to publish")
        return

    # Fetch content. If lookup fails, release the lock immediately so the row
    # doesn't stay stuck in processing.
    try:
        content = get_content(supabase, item["content_id"])
    except Exception as exc:
        error_str = _redact(str(exc))
        log.error(f"Failed to fetch content for queue item {item['id']}: {error_str}")
        mark_failed_or_retry(
            supabase,
            queue_id=item["id"],
            error=f"Content fetch failed: {error_str}",
            attempt_count=item["attempt_count"],
            max_attempts=item["max_attempts"],
        )
        sys.exit(1)

    process_item(supabase, item, content)


if __name__ == "__main__":
    main()

# scripts/

## Safety Matrix

| Location | Files | Who Calls It | Can Mutate Supabase |
| --- | --- | --- | --- |
| `scripts/` (root) | `instaautopost_publisher.py`, `requirements.txt` | GitHub Actions workflow only | Yes — queue and attempt tables, via service role |
| `scripts/admin/` | `generate_schedule_slots.py`, `assign_content_to_schedule_slots.py`, `schedule_draft_content.py`, `report_orphan_storage_files.py` | Operator manually from local machine | `generate_schedule_slots.py`, `assign_content_to_schedule_slots.py`, `schedule_draft_content.py` mutate Supabase when `--execute` is passed. `report_orphan_storage_files.py` is **report-only and never mutates**. |
| `scripts/local/` | `analyze_raw_media.py`, `prepare_test_video_batch.py`, `prepare_test_carousels.py`, `import_travel_test_batch.py`, `fix_video_post_002.py` | Developer manually from local machine | `import_travel_test_batch.py` and `fix_video_post_002.py` write to Supabase Storage and `ig_content_library` when `--execute` is passed. The others are local-only (no network calls). |

## Rules

- **The GitHub Actions workflow (`.github/workflows/instaautopost-publisher.yml`) must call only `scripts/instaautopost_publisher.py`.** It must never call scripts in `scripts/admin/` or `scripts/local/`.
- `scripts/admin/` scripts are production-sensitive: they can insert or update `ig_schedule_slots` and `ig_publishing_queue` when `--execute` is used. Run them only against the intended Supabase environment. All are dry-run by default.
- `scripts/local/` scripts must not target production Supabase unless you explicitly intend a test import. `import_travel_test_batch.py` and `fix_video_post_002.py` write real rows when `--execute` is passed — verify `SUPABASE_URL` points to the correct project first.
- `scripts/local/analyze_raw_media.py`, `prepare_test_video_batch.py`, and `prepare_test_carousels.py` make no network calls and do not touch Supabase or Instagram.
- No script in `scripts/admin/` or `scripts/local/` publishes to Instagram or triggers GitHub Actions. The only Instagram publishing script is `scripts/instaautopost_publisher.py`, and live publishing remains gated by the publisher workflow and live-mode safeguards.
- `scripts/admin/report_orphan_storage_files.py` is **report-only**: it lists Storage objects in `instaautopost-media` that are not referenced by any `ig_content_library` row and are older than a configurable grace period (default: 24h). It never deletes files. Destructive cleanup is not implemented — any deletion must be a future explicit reviewed operation.

## Production Automation

Only `scripts/instaautopost_publisher.py` is part of production automation. It is called by the publisher workflow and must remain at the scripts root.

`scripts/requirements.txt` is the dependency file for all scripts.

# Instagram API Notes

## Scope

These notes apply to InstaAutoPost's Instagram Graph API publishing flow.

The Python worker is the only component that should call Instagram publishing endpoints. The React UI should manage state only.

## High-Level Publishing Flow

Live publishing flow:

```text
create media container
  -> poll media container status
  -> publish media container
  -> receive media_id
  -> store completion proof in Supabase
```

Current worker endpoints conceptually used:

- `POST /{ig-user-id}/media`
- `GET /{container-id}?fields=status_code,status`
- `POST /{ig-user-id}/media_publish`

## Required Environment Variables

Names only:

- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `IG_USER_ID`
- `IG_ACCESS_TOKEN`
- `INSTAGRAM_API_ENABLED`

Never document or print real values.

## Live Mode Gate

Live publishing is allowed only when:

```text
INSTAGRAM_API_ENABLED=true
```

Any other value should be treated as dry-run mode.

## Dry-Run Mode

Dry-run mode applies when:

```text
INSTAGRAM_API_ENABLED=false
```

or when the variable is unset or anything other than exact `true`.

Dry-run must not call Instagram endpoints.

## Secret And URL Safety

Never log:

- `IG_ACCESS_TOKEN`
- `SUPABASE_SERVICE_ROLE_KEY`
- Bearer tokens.
- Access token query params.
- Signed URL query params.

If a `video_url` may be signed, log only a redacted version without query parameters.

Safe to log when needed:

- Queue ID.
- Attempt number.
- Worker version.
- HTTP status category.
- Instagram container ID.
- Instagram media ID after successful publish.

## Error Handling Principles

- API errors before `media_id` can be retryable.
- API errors should be redacted before storing in attempts or queue state.
- Once a real `media_id` exists, local database/logging errors must not trigger a normal retry.
- Failed container status should mark or retry the queue item according to retry rules.
- Timeout while polling should be treated as uncertain until verified if a container was created.

## First Real Publish Safety Checklist

- [ ] User explicitly confirms live publish.
- [ ] Automatic workflow schedule state is intentional.
- [ ] Dry-run succeeds on the selected queue row.
- [ ] Queue row points to the correct content.
- [ ] Content `video_url` is publicly accessible to Instagram.
- [ ] Caption and hashtags are final.
- [ ] `IG_USER_ID` is configured.
- [ ] `IG_ACCESS_TOKEN` is configured.
- [ ] Tokens are not printed in logs.
- [ ] Signed URLs are redacted in logs.
- [ ] Worker will not retry after receiving `media_id`.
- [ ] Stale `processing` recovery is fixed.
- [ ] Schema drift is resolved.


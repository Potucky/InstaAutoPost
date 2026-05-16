# InstaAutoPost

Instagram Autoposting Control Center — a production-grade backend publishing factory backed by Supabase.

## Architecture

| Layer | Component | Responsibility |
|-------|-----------|----------------|
| Database | Supabase (PostgreSQL) | Source of truth for all content and queue state |
| UI | Vite + React + TypeScript | Manage content and queue records — never publishes |
| Worker | `scripts/instaautopost_publisher.py` | Owns Instagram Graph API publishing |
| Scheduler | GitHub Actions cron | Triggers worker every 5 minutes |

## Project Structure

```
InstaAutoPost/
├── docs/
│   └── INSTAAUTOPOST_FACTORY.md       # Full architecture reference
├── scripts/
│   ├── instaautopost_publisher.py     # Backend publisher worker
│   └── requirements.txt
├── supabase/
│   ├── migrations/
│   │   └── 20260516000000_create_instaautopost_schema.sql
│   └── policies/
│       └── instaautopost_dev_rls_policies.sql
├── .github/
│   └── workflows/
│       └── instaautopost-publisher.yml
└── ui/                                # Vite + React dashboard
```

## Quick Start

### 1. Apply Supabase Migrations

Both the schema and dev RLS policies are applied through migrations in `supabase/migrations/`:

- `20260516000000_create_instaautopost_schema.sql` — tables, indexes, enums, RPC function
- `20260516001000_add_instaautopost_dev_rls_policies.sql` — dev RLS policies (authenticated users)

```bash
# Via Supabase CLI (applies all pending migrations in order)
supabase db push

# Or via Supabase Dashboard SQL editor — apply each file in order
```

> **UI Note**: Dev RLS policies target the `authenticated` role. The UI requires an active
> Supabase session (a logged-in user) to read or write any data. Without auth, the browser
> client will see empty results or permission errors.

### 2. Run the UI Locally

```bash
cd ui
cp .env.example .env.local
# Fill in VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY
npm install
npm run dev
```

### 3. Run the Worker (Dry Run)

The worker uses the service role key and bypasses RLS — it can be tested without a UI
session as long as seed rows exist in `ig_publishing_queue`.

```bash
cd scripts
pip install -r requirements.txt
export SUPABASE_URL=your_url
export SUPABASE_SERVICE_ROLE_KEY=your_key
# INSTAGRAM_API_ENABLED is not set → dry-run mode
python instaautopost_publisher.py
```

### 4. Run the Worker (Live)

```bash
export INSTAGRAM_API_ENABLED=true
export IG_USER_ID=your_ig_user_id
export IG_ACCESS_TOKEN=your_long_lived_token
python instaautopost_publisher.py
```

## Required Secrets / Variables

### GitHub Actions Secrets

| Name | Type | Description |
|------|------|-------------|
| `SUPABASE_URL` | Secret | Supabase project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | Secret | Service role key (backend only) |
| `IG_USER_ID` | Secret | Instagram Business User ID |
| `IG_ACCESS_TOKEN` | Secret | Long-lived Instagram access token |
| `INSTAGRAM_API_ENABLED` | Variable | Set to `true` to enable live publishing |

### UI Environment Variables

| Name | Description |
|------|-------------|
| `VITE_SUPABASE_URL` | Supabase project URL |
| `VITE_SUPABASE_ANON_KEY` | Supabase anon key (public, safe for browser) |

> **Security**: The service role key is never used in the frontend. Only the anon key is used in the browser.

## Known TODOs

- [ ] Add Supabase Auth (login page, user sessions)
- [ ] Restrict RLS policies to `auth.uid()` owner checks for production
- [ ] Add Instagram token refresh automation
- [ ] Add video file upload to Supabase Storage (currently uses external video URLs)
- [ ] Add thumbnail generation
- [ ] Add Slack/webhook notifications on publish success/failure
- [ ] Add analytics charts to Dashboard
- [ ] Add bulk scheduling from Content Library
- [ ] Add calendar drag-and-drop rescheduling
- [ ] Add rate limiting guard (Instagram API limits)

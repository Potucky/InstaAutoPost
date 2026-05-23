// trigger-publish — Supabase Edge Function
//
// Accepts { queue_id } from an authenticated UI session.
// Validates the queue row server-side, then dispatches the GitHub Actions
// workflow with live_mode=true for exactly that queue_id.
//
// Required secrets (set via: supabase secrets set KEY=value):
//   GITHUB_PAT   — Fine-grained PAT with Actions: Read and write on this repo.
//
// Optional env vars (defaults shown):
//   GITHUB_OWNER — defaults to "Potucky"
//   GITHUB_REPO  — defaults to "InstaAutoPost"
//
// Auto-injected by Supabase (do not set manually):
//   SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, SUPABASE_ANON_KEY

import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const CORS_HEADERS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers":
    "authorization, x-client-info, apikey, content-type",
};

const JSON_HEADERS = {
  ...CORS_HEADERS,
  "Content-Type": "application/json",
};

const ELIGIBLE_STATUSES = [
  "ready",
  "scheduled",
  "retry_scheduled",
  "processing",
];

function jsonResponse(body: unknown, status: number): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: JSON_HEADERS,
  });
}

Deno.serve(async (req: Request) => {
  // Handle CORS preflight
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: CORS_HEADERS });
  }

  if (req.method !== "POST") {
    return jsonResponse({ error: "Method not allowed" }, 405);
  }

  // Require authenticated session — supabase.functions.invoke() sends the
  // user JWT automatically as Authorization: Bearer <token>.
  const authHeader = req.headers.get("Authorization");
  if (!authHeader?.startsWith("Bearer ")) {
    return jsonResponse({ error: "Unauthorized" }, 401);
  }

  // Parse and validate request body
  let queue_id: string;
  try {
    const body = await req.json();
    queue_id = body?.queue_id;
  } catch {
    return jsonResponse({ error: "Invalid request body" }, 400);
  }

  if (!queue_id || typeof queue_id !== "string" || queue_id.trim() === "") {
    return jsonResponse({ error: "queue_id is required" }, 400);
  }

  const supabaseUrl = Deno.env.get("SUPABASE_URL")!;
  const serviceKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
  const anonKey = Deno.env.get("SUPABASE_ANON_KEY")!;

  // Verify the caller's JWT is a valid active session
  const userToken = authHeader.slice("Bearer ".length);
  const userClient = createClient(supabaseUrl, anonKey, {
    global: { headers: { Authorization: `Bearer ${userToken}` } },
  });

  const {
    data: { user },
    error: authError,
  } = await userClient.auth.getUser();

  if (authError || !user) {
    return jsonResponse({ error: "Invalid or expired session" }, 401);
  }

  // Validate queue row with service role (bypasses RLS)
  const adminClient = createClient(supabaseUrl, serviceKey);

  const { data: row, error: rowError } = await adminClient
    .from("ig_publishing_queue")
    .select(
      "id, queue_status, published_at, external_media_id, attempt_count, max_attempts, created_by",
    )
    .eq("id", queue_id)
    .single();

  if (rowError || !row) {
    return jsonResponse({ error: "Queue item not found" }, 404);
  }

  // Ownership check: the queue row must have been created by the authenticated user.
  // created_by is set to auth.uid() when the UI inserts the row.
  // If null or mismatched, ownership cannot be verified — reject rather than allow.
  if (!row.created_by || row.created_by !== user.id) {
    return jsonResponse(
      { error: "You do not have permission to publish this item" },
      403,
    );
  }

  if (row.published_at || row.external_media_id) {
    return jsonResponse({ error: "This video has already been published" }, 409);
  }

  if (!ELIGIBLE_STATUSES.includes(row.queue_status)) {
    return jsonResponse(
      {
        error: `Queue item is not eligible for publishing (status: ${row.queue_status})`,
      },
      409,
    );
  }

  if (row.attempt_count >= row.max_attempts) {
    return jsonResponse(
      { error: "Queue item has reached its maximum retry limit" },
      409,
    );
  }

  // Trigger the GitHub Actions workflow
  const githubPat = Deno.env.get("GITHUB_PAT");
  if (!githubPat) {
    console.error("GITHUB_PAT secret is not configured");
    return jsonResponse({ error: "Publish service is not configured" }, 500);
  }

  const owner = Deno.env.get("GITHUB_OWNER") ?? "Potucky";
  const repo = Deno.env.get("GITHUB_REPO") ?? "InstaAutoPost";
  const dispatchUrl =
    `https://api.github.com/repos/${owner}/${repo}/actions/workflows/instaautopost-publisher.yml/dispatches`;

  const ghResp = await fetch(dispatchUrl, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${githubPat}`,
      Accept: "application/vnd.github+json",
      "X-GitHub-Api-Version": "2022-11-28",
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      ref: "main",
      inputs: {
        queue_id: queue_id,
        live_mode: "true",
      },
    }),
  });

  if (!ghResp.ok) {
    // Never log PAT or response body — either can contain sensitive context.
    console.error(
      `GitHub workflow dispatch failed: HTTP ${ghResp.status} for queue_id=${queue_id}`,
    );
    return jsonResponse(
      { error: "Failed to trigger publish workflow — check configuration" },
      502,
    );
  }

  return jsonResponse({ ok: true, queue_id }, 200);
});

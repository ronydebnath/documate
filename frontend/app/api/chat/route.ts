// Server-side proxy to FastAPI. Keeps the API_URL and demo key off the
// client bundle.

const DEFAULT_API_URL = "http://127.0.0.1:8000";

export async function POST(req: Request): Promise<Response> {
  const apiUrl = process.env.API_URL || DEFAULT_API_URL;
  const demoKey = process.env.DEMO_KEY || "";
  const body = await req.text();

  const headers: Record<string, string> = { "content-type": "application/json" };
  if (demoKey) headers["x-demo-key"] = demoKey;

  try {
    const upstream = await fetch(`${apiUrl}/chat`, {
      method: "POST",
      headers,
      body,
      // Generous timeout. Fly.io is configured with auto_stop_machines, so
      // the first request after idle has to: (a) wait for Fly to start the
      // machine (~5-10s), then (b) load the BGE embedder from the baked HF
      // cache (~6s). Capped at 55s (just under Vercel Hobby's 60s
      // function ceiling) so the Vercel proxy returns a clean 502 before
      // the platform itself kills the function.
      signal: AbortSignal.timeout(55_000),
    });
    const text = await upstream.text();
    return new Response(text, {
      status: upstream.status,
      headers: { "content-type": "application/json" },
    });
  } catch (err) {
    const message =
      err instanceof Error ? err.message : "Unknown upstream error";
    return new Response(
      JSON.stringify({ detail: `Backend unreachable: ${message}` }),
      { status: 502, headers: { "content-type": "application/json" } }
    );
  }
}

export const runtime = "nodejs";
// Vercel function ceiling. Hobby tier max is 60s; we ask for 60 and abort
// upstream at 55s (see AbortSignal above) so we control the failure shape
// instead of getting cut off mid-stream.
export const maxDuration = 60;

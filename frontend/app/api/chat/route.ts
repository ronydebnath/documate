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
      // Generous timeout: the first request after a cold backend has to load
      // the embedder weights (~6s).
      signal: AbortSignal.timeout(45_000),
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

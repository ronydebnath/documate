import type { ChatRequest, ChatResponse } from "./types";

export async function postChat(query: string, signal?: AbortSignal): Promise<ChatResponse> {
  const body: ChatRequest = { query };
  const r = await fetch("/api/chat", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });
  if (!r.ok) {
    let detail = "";
    try {
      detail = (await r.text()).slice(0, 500);
    } catch {
      // ignore
    }
    throw new Error(`Request failed (${r.status}): ${detail || r.statusText}`);
  }
  return (await r.json()) as ChatResponse;
}

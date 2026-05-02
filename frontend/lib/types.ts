// Mirrors backend/app/schemas.py. Keep in sync.

export interface Citation {
  chunk_id: string;
  source_url: string;
  title: string;
  snippet: string;
}

export interface LatencyInfo {
  retrieve: number;
  generate: number;
  total: number;
}

export interface ChatRequest {
  query: string;
  history?: Array<Record<string, unknown>>;
}

export interface ChatResponse {
  answer: string;
  citations: Citation[];
  retrieved_chunk_ids: string[];
  latency_ms: LatencyInfo;
}

export interface HealthResponse {
  status: string;
  collection_size: number;
  generator_model: string;
  embedding_model: string;
}

// UI-side types

export type Role = "user" | "assistant";

export interface ChatTurn {
  id: string;
  role: Role;
  content: string;
  citations?: Citation[];
  retrievedChunkIds?: string[];
  latency?: LatencyInfo;
  loading?: boolean;
  error?: string;
}

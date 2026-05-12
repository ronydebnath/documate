"use client";

import { useCallback, useState } from "react";

import { MessageInput } from "@/components/MessageInput";
import { MessageList } from "@/components/MessageList";
import { SourceDrawer } from "@/components/SourceDrawer";
import { postChat } from "@/lib/api";
import type { ChatTurn, Citation } from "@/lib/types";

const SUGGESTIONS = [
  "How much notice do I give when resigning after 2 years?",
  "Do casual employees get paid annual leave?",
  "What types of leave are in the National Employment Standards?",
  "When does overtime apply?",
];

function newId(): string {
  return Math.random().toString(36).slice(2, 10);
}

export default function ChatPage() {
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [input, setInput] = useState("");
  const [pending, setPending] = useState(false);
  const [drawer, setDrawer] = useState<(Citation & { index: number }) | null>(
    null
  );

  const submit = useCallback(
    async (raw?: string) => {
      const query = (raw ?? input).trim();
      if (!query || pending) return;

      const userTurn: ChatTurn = { id: newId(), role: "user", content: query };
      const placeholder: ChatTurn = {
        id: newId(),
        role: "assistant",
        content: "",
        loading: true,
      };
      setTurns((t) => [...t, userTurn, placeholder]);
      setInput("");
      setPending(true);

      try {
        const resp = await postChat(query);
        setTurns((t) =>
          t.map((turn) =>
            turn.id === placeholder.id
              ? {
                  ...turn,
                  content: resp.answer,
                  citations: resp.citations,
                  retrievedChunkIds: resp.retrieved_chunk_ids,
                  latency: resp.latency_ms,
                  loading: false,
                }
              : turn
          )
        );
      } catch (err) {
        const msg = err instanceof Error ? err.message : "Unknown error";
        setTurns((t) =>
          t.map((turn) =>
            turn.id === placeholder.id
              ? { ...turn, loading: false, error: msg }
              : turn
          )
        );
      } finally {
        setPending(false);
      }
    },
    [input, pending]
  );

  const handleCitationClick = useCallback(
    (c: Citation, index: number) => setDrawer({ ...c, index }),
    []
  );

  const isEmpty = turns.length === 0;

  return (
    <div className="flex h-screen flex-col">
      <Header />

      <main className="relative flex-1 overflow-hidden">
        {isEmpty ? (
          <EmptyState
            onPick={(q) => {
              setInput(q);
              submit(q);
            }}
          />
        ) : (
          <MessageList turns={turns} onCitationClick={handleCitationClick} />
        )}

        {/* Composer pinned to bottom */}
        <div className="pointer-events-none absolute inset-x-0 bottom-0">
          <div className="bg-gradient-to-t from-zinc-50 via-zinc-50/85 to-transparent pb-4 pt-10">
            <div className="pointer-events-auto mx-auto max-w-prose px-4 sm:px-6">
              <MessageInput
                value={input}
                onChange={setInput}
                onSubmit={submit}
                disabled={pending}
              />
            </div>
          </div>
        </div>
      </main>

      <SourceDrawer
        citation={drawer}
        onClose={() => setDrawer(null)}
      />

      <Footer />
    </div>
  );
}

function Footer() {
  return (
    <footer className="border-t border-zinc-200/80 bg-white/60 px-4 py-2 text-center text-[11px] text-zinc-500 sm:px-6">
      Built by{" "}
      <a
        href="https://www.linkedin.com/in/ronydebnath/"
        target="_blank"
        rel="noopener noreferrer"
        className="font-medium text-zinc-700 underline decoration-zinc-200 decoration-2 underline-offset-4 transition hover:text-zinc-900 hover:decoration-zinc-900"
      >
        Rony Debnath
      </a>
    </footer>
  );
}

function Header() {
  return (
    <header className="border-b border-zinc-200/80 bg-white/70 backdrop-blur supports-[backdrop-filter]:bg-white/55">
      <div className="mx-auto flex max-w-prose items-center justify-between px-4 py-3 sm:px-6">
        <div className="flex items-center gap-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-zinc-900 text-white">
            <svg
              width="16"
              height="16"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden="true"
            >
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
              <polyline points="14 2 14 8 20 8" />
              <line x1="9" y1="13" x2="15" y2="13" />
              <line x1="9" y1="17" x2="15" y2="17" />
            </svg>
          </div>
          <div className="leading-tight">
            <p className="text-sm font-semibold text-zinc-900">DocuMate</p>
            <p className="text-[11px] text-zinc-500">
              Fair Work Australia · with citations
            </p>
          </div>
        </div>

        <a
          href="https://www.fairwork.gov.au/"
          target="_blank"
          rel="noopener noreferrer"
          className="hidden text-[11px] text-zinc-500 underline decoration-zinc-200 decoration-2 underline-offset-4 hover:text-zinc-900 hover:decoration-zinc-900 sm:inline-block"
        >
          fairwork.gov.au
        </a>
      </div>
    </header>
  );
}

function EmptyState({ onPick }: { onPick: (q: string) => void }) {
  return (
    <div className="mx-auto flex h-full max-w-prose flex-col items-start justify-center px-4 pb-40 sm:px-6">
      <span className="rounded-full border border-zinc-200 bg-white px-2.5 py-0.5 text-[11px] font-medium text-zinc-600">
        Ask about Australian workplace rules
      </span>
      <h1 className="mt-5 text-3xl font-semibold leading-tight tracking-tight text-zinc-900 sm:text-4xl">
        Plain answers,
        <br />
        with the source.
      </h1>
      <p className="mt-3 max-w-md text-[15px] leading-7 text-zinc-600">
        DocuMate retrieves passages from{" "}
        <span className="font-medium text-zinc-800">Fair Work Ombudsman</span>{" "}
        documents and uses them to answer your question. Every claim links back
        to the source.
      </p>

      <div className="mt-8 grid w-full grid-cols-1 gap-2 sm:grid-cols-2">
        {SUGGESTIONS.map((q) => (
          <button
            key={q}
            type="button"
            onClick={() => onPick(q)}
            className="group flex items-center justify-between gap-3 rounded-xl border border-zinc-200 bg-white px-4 py-3 text-left text-sm text-zinc-700 shadow-sm transition hover:border-zinc-300 hover:bg-zinc-50 hover:text-zinc-900 focus:outline-none focus-visible:ring-2 focus-visible:ring-zinc-900"
          >
            <span className="line-clamp-2">{q}</span>
            <svg
              width="14"
              height="14"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden="true"
              className="shrink-0 text-zinc-400 transition group-hover:translate-x-0.5 group-hover:text-zinc-700"
            >
              <line x1="5" y1="12" x2="19" y2="12" />
              <polyline points="12 5 19 12 12 19" />
            </svg>
          </button>
        ))}
      </div>
    </div>
  );
}

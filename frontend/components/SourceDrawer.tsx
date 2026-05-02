"use client";

import { useEffect } from "react";

import type { Citation } from "@/lib/types";

interface SourceDrawerProps {
  citation: (Citation & { index: number }) | null;
  onClose: () => void;
}

export function SourceDrawer({ citation, onClose }: SourceDrawerProps) {
  // Esc to close
  useEffect(() => {
    if (!citation) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [citation, onClose]);

  const open = citation !== null;

  return (
    <>
      {/* Backdrop */}
      <div
        aria-hidden={!open}
        onClick={onClose}
        className={`fixed inset-0 z-40 bg-zinc-950/30 backdrop-blur-[2px] transition-opacity duration-200 ${
          open ? "opacity-100" : "pointer-events-none opacity-0"
        }`}
      />

      {/* Panel */}
      <aside
        role="dialog"
        aria-modal="true"
        aria-label="Source detail"
        className={`fixed right-0 top-0 z-50 flex h-full w-full max-w-md flex-col border-l border-zinc-200 bg-white shadow-2xl transition-transform duration-300 ease-out ${
          open ? "translate-x-0" : "translate-x-full"
        }`}
      >
        <header className="flex items-start justify-between gap-4 border-b border-zinc-100 px-6 py-5">
          <div className="min-w-0">
            <p className="text-[11px] font-semibold uppercase tracking-wider text-zinc-500">
              Source {citation?.index}
            </p>
            <h2 className="mt-1 break-words text-lg font-semibold leading-tight text-zinc-900">
              {citation?.title || "—"}
            </h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close source panel"
            className="rounded-md p-1.5 text-zinc-500 transition hover:bg-zinc-100 hover:text-zinc-900 focus:outline-none focus-visible:ring-2 focus-visible:ring-zinc-900"
          >
            <svg
              width="18"
              height="18"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden="true"
            >
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </header>

        <div className="flex-1 overflow-y-auto px-6 py-5">
          {citation ? (
            <>
              <section>
                <p className="text-[11px] font-semibold uppercase tracking-wider text-zinc-500">
                  Excerpt
                </p>
                <p className="mt-2 whitespace-pre-line text-sm leading-relaxed text-zinc-800">
                  {citation.snippet}
                </p>
              </section>

              <section className="mt-6">
                <p className="text-[11px] font-semibold uppercase tracking-wider text-zinc-500">
                  Chunk ID
                </p>
                <p className="mt-2 font-mono text-xs text-zinc-600">
                  {citation.chunk_id}
                </p>
              </section>

              <section className="mt-6">
                <p className="text-[11px] font-semibold uppercase tracking-wider text-zinc-500">
                  Source URL
                </p>
                <a
                  href={citation.source_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="mt-2 inline-flex items-center gap-1.5 break-all text-sm font-medium text-zinc-900 underline decoration-zinc-300 decoration-2 underline-offset-4 hover:decoration-zinc-900"
                >
                  {citation.source_url}
                  <svg
                    width="13"
                    height="13"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    aria-hidden="true"
                    className="shrink-0"
                  >
                    <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
                    <polyline points="15 3 21 3 21 9" />
                    <line x1="10" y1="14" x2="21" y2="3" />
                  </svg>
                </a>
              </section>
            </>
          ) : null}
        </div>

        <footer className="border-t border-zinc-100 px-6 py-3 text-[11px] text-zinc-500">
          Press <kbd className="rounded border border-zinc-200 bg-zinc-50 px-1.5 py-0.5 font-mono">Esc</kbd> to close
        </footer>
      </aside>
    </>
  );
}

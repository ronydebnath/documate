"use client";

import type { Citation } from "@/lib/types";

interface CitationChipProps {
  index: number;
  citation: Citation;
  onClick: () => void;
}

export function CitationChip({ index, citation, onClick }: CitationChipProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="group inline-flex items-center gap-1.5 rounded-full border border-zinc-200 bg-white px-2.5 py-1 text-xs text-zinc-700 shadow-sm transition hover:border-zinc-300 hover:bg-zinc-50 hover:text-zinc-900 focus:outline-none focus-visible:ring-2 focus-visible:ring-zinc-900 focus-visible:ring-offset-1"
      aria-label={`Source ${index}: ${citation.title}`}
    >
      <span className="font-mono text-[10px] font-semibold tabular-nums text-zinc-500 group-hover:text-zinc-700">
        {index}
      </span>
      <span className="max-w-[16rem] truncate font-medium">{citation.title}</span>
    </button>
  );
}

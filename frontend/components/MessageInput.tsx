"use client";

import { useEffect, useRef } from "react";

interface MessageInputProps {
  value: string;
  onChange: (v: string) => void;
  onSubmit: () => void;
  disabled?: boolean;
}

export function MessageInput({
  value,
  onChange,
  onSubmit,
  disabled,
}: MessageInputProps) {
  const ref = useRef<HTMLTextAreaElement | null>(null);

  // Auto-resize textarea up to a cap.
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 180) + "px";
  }, [value]);

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        if (!disabled && value.trim()) onSubmit();
      }}
      className="relative"
    >
      <div className="flex items-end gap-2 rounded-2xl border border-zinc-200 bg-white p-2.5 shadow-sm transition focus-within:border-zinc-400 focus-within:shadow-md">
        <textarea
          ref={ref}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              if (!disabled && value.trim()) onSubmit();
            }
          }}
          placeholder="Ask about leave, notice periods, pay, awards..."
          rows={1}
          disabled={false}
          aria-label="Question"
          className="flex-1 resize-none bg-transparent px-2 py-1.5 text-[15px] leading-6 text-zinc-900 placeholder:text-zinc-400 focus:outline-none disabled:opacity-60"
        />
        <button
          type="submit"
          disabled={disabled || !value.trim()}
          aria-label="Send"
          className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-zinc-900 text-white transition hover:bg-zinc-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-zinc-900 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:bg-zinc-300"
        >
          <svg
            width="16"
            height="16"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2.2"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden="true"
          >
            <path d="M5 12h14M13 5l7 7-7 7" />
          </svg>
        </button>
      </div>
      <p className="mt-2 px-1 text-[11px] text-zinc-500">
        Press <kbd className="rounded border border-zinc-200 bg-white px-1.5 py-0.5 font-mono text-[10px]">Enter</kbd> to send · <kbd className="rounded border border-zinc-200 bg-white px-1.5 py-0.5 font-mono text-[10px]">Shift</kbd>+<kbd className="rounded border border-zinc-200 bg-white px-1.5 py-0.5 font-mono text-[10px]">Enter</kbd> for newline
      </p>
    </form>
  );
}

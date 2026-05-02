"use client";

import { useEffect, useMemo, useRef } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import type { ChatTurn, Citation } from "@/lib/types";

import { CitationChip } from "./CitationChip";

interface MessageListProps {
  turns: ChatTurn[];
  onCitationClick: (c: Citation, index: number) => void;
}

const CHUNK_ID_RE = /\[[a-z0-9][a-z0-9-]*::\d{4}\]/g;

function escapeRegex(s: string): string {
  return s.replace(/[-/\\^$*+?.()|[\]{}]/g, "\\$&");
}

/**
 * Replace inline `[chunk_id]` citations with `[N]` numbers matching the
 * citations array order (1-based). Strip any leftover chunk-id-shaped
 * brackets that the backend dropped as hallucinated.
 */
function transformAnswer(answer: string, citations: Citation[]): string {
  let out = answer;
  citations.forEach((c, i) => {
    const re = new RegExp("\\[" + escapeRegex(c.chunk_id) + "\\]", "g");
    out = out.replace(re, `[${i + 1}]`);
  });
  return out.replace(CHUNK_ID_RE, "");
}

export function MessageList({ turns, onCitationClick }: MessageListProps) {
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const stickToBottomRef = useRef(true);

  // Track whether the user is near the bottom; if so, keep auto-scrolling.
  const onScroll = () => {
    const el = scrollRef.current;
    if (!el) return;
    const distance = el.scrollHeight - el.scrollTop - el.clientHeight;
    stickToBottomRef.current = distance < 80;
  };

  useEffect(() => {
    if (stickToBottomRef.current) {
      const el = scrollRef.current;
      if (el) el.scrollTop = el.scrollHeight;
    }
  }, [turns]);

  return (
    <div
      ref={scrollRef}
      onScroll={onScroll}
      aria-live="polite"
      aria-relevant="additions"
      className="h-full overflow-y-auto"
    >
      <div className="mx-auto max-w-prose px-4 pb-32 pt-8 sm:px-6">
        <ol className="space-y-8">
          {turns.map((turn) => (
            <li key={turn.id}>
              {turn.role === "user" ? (
                <UserBubble content={turn.content} />
              ) : (
                <AssistantBubble turn={turn} onCitationClick={onCitationClick} />
              )}
            </li>
          ))}
        </ol>
      </div>
    </div>
  );
}

function UserBubble({ content }: { content: string }) {
  return (
    <div className="flex justify-end">
      <article className="max-w-[80%] rounded-2xl rounded-br-md bg-zinc-900 px-4 py-2.5 text-[15px] leading-6 text-white shadow-sm">
        {content}
      </article>
    </div>
  );
}

function AssistantBubble({
  turn,
  onCitationClick,
}: {
  turn: ChatTurn;
  onCitationClick: (c: Citation, index: number) => void;
}) {
  const transformed = useMemo(
    () => (turn.content ? transformAnswer(turn.content, turn.citations || []) : ""),
    [turn.content, turn.citations]
  );

  if (turn.error) {
    return (
      <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-900">
        <p className="font-medium">Couldn't reach the backend</p>
        <p className="mt-1 text-red-800/80">{turn.error}</p>
      </div>
    );
  }

  if (turn.loading) {
    return (
      <div className="flex items-center gap-3 text-zinc-500">
        <span className="flex gap-1">
          <Dot delay="0ms" />
          <Dot delay="160ms" />
          <Dot delay="320ms" />
        </span>
        <span className="text-sm">Thinking...</span>
      </div>
    );
  }

  return (
    <article className="space-y-4">
      <div className="prose-zinc prose-sm max-w-none">
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          components={{
            a: ({ href, children, ...rest }) => {
              const safe =
                typeof href === "string" &&
                (href.startsWith("http://") || href.startsWith("https://"));
              return safe ? (
                <a
                  href={href}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-zinc-900 underline decoration-zinc-300 decoration-2 underline-offset-4 hover:decoration-zinc-900"
                  {...rest}
                >
                  {children}
                </a>
              ) : (
                <span>{children}</span>
              );
            },
            h1: ({ children }) => (
              <h2 className="mt-2 text-lg font-semibold text-zinc-900">{children}</h2>
            ),
            h2: ({ children }) => (
              <h3 className="mt-4 text-base font-semibold text-zinc-900">{children}</h3>
            ),
            h3: ({ children }) => (
              <h4 className="mt-3 text-sm font-semibold uppercase tracking-wide text-zinc-700">
                {children}
              </h4>
            ),
            p: ({ children }) => (
              <p className="text-[15px] leading-7 text-zinc-800">{children}</p>
            ),
            ul: ({ children }) => (
              <ul className="ml-5 list-disc space-y-1.5 text-[15px] leading-7 text-zinc-800 marker:text-zinc-400">
                {children}
              </ul>
            ),
            ol: ({ children }) => (
              <ol className="ml-5 list-decimal space-y-1.5 text-[15px] leading-7 text-zinc-800 marker:text-zinc-400">
                {children}
              </ol>
            ),
            li: ({ children }) => <li className="pl-1">{children}</li>,
            strong: ({ children }) => (
              <strong className="font-semibold text-zinc-900">{children}</strong>
            ),
            blockquote: ({ children }) => (
              <blockquote className="border-l-2 border-zinc-200 pl-4 text-zinc-600">
                {children}
              </blockquote>
            ),
            code: ({ children }) => (
              <code className="rounded bg-zinc-100 px-1 py-0.5 font-mono text-[12px] text-zinc-800">
                {children}
              </code>
            ),
          }}
        >
          {transformed}
        </ReactMarkdown>
      </div>

      {turn.citations && turn.citations.length > 0 ? (
        <div className="flex flex-wrap gap-2 pt-1">
          {turn.citations.map((c, i) => (
            <CitationChip
              key={c.chunk_id + ":" + i}
              index={i + 1}
              citation={c}
              onClick={() => onCitationClick(c, i + 1)}
            />
          ))}
        </div>
      ) : null}

      {turn.latency ? (
        <p className="text-[11px] text-zinc-400">
          Retrieved in {turn.latency.retrieve}ms · Answered in {turn.latency.generate}ms · Total {turn.latency.total}ms
        </p>
      ) : null}
    </article>
  );
}

function Dot({ delay }: { delay: string }) {
  return (
    <span
      style={{ animationDelay: delay }}
      className="inline-block h-2 w-2 animate-pulse rounded-full bg-zinc-400"
    />
  );
}

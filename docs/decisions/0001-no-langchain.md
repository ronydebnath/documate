# ADR-0001: Don't use LangChain (or similar RAG frameworks)

- **Status:** Accepted
- **Date:** 2026-04-22

## Context

DocuMate is a small RAG app: one corpus, one retriever, one generator, one UI. The mainstream way to build this in 2026 is LangChain or LlamaIndex. Both offer fast scaffolding, built-in chunkers, retrievers, chains, and LLM wrappers.

For a portfolio project aimed at a senior data/GenAI engineering role, "fast scaffolding" is not the main optimization. What matters is whether a reader (interviewer, reviewer) can see the system's actual behavior and engineering decisions.

## Decision

Use the Anthropic SDK directly for generation and judging, and `sentence-transformers` directly for embeddings. Write our own ~200 lines for chunking, retrieval, prompt assembly, and generation. ChromaDB is used as a thin vector store — we don't wrap it in LangChain's `VectorStoreRetriever`. The choice of `BAAI/bge-small-en-v1.5` over hosted embedding APIs is documented separately in [ADR-0003](./0003-bge-over-openai-embeddings.md).

## Consequences

### Positive

- **Readable surface area.** Every retrieval or prompt behavior is visible in ~200 lines of project code, not distributed across a framework's abstractions.
- **Debuggable.** When something misbehaves (wrong chunks retrieved, prompt not assembled correctly), the stack trace points into our code, not into three layers of generic runnables.
- **Smaller blast radius for upgrades.** Anthropic / OpenAI SDK bumps are independent; we aren't pinned to whatever version LangChain currently tolerates.
- **Signals engineering judgment.** A portfolio that shows "I picked the tool, I understand what it costs me to avoid the framework" reads as more senior than "I used the default stack."

### Negative

- We write our own chunker, retriever wrapper, and eval harness. ~1 day of work that LangChain would save on Day 1.
- If scope grows (multi-tenant, tool-using agents, complex chains), the "write it ourselves" decision will have to be revisited.
- We don't get LangChain's integrations for free (e.g. if we later want Serper search or Confluence loaders, we'd write those too).

### When to revisit

Revisit this ADR if any of these become true:
- We need >3 agent tools chained with branching logic.
- We want to swap LLM providers frequently and benefit from a uniform interface.
- The project grows past ~1500 LoC of hand-rolled RAG plumbing.

Until then: direct SDK calls.

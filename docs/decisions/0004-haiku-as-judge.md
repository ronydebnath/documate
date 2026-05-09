# ADR-0004: Claude Haiku 4.5 as the eval judge

- **Status:** Accepted
- **Date:** 2026-04-30

## Context

The eval harness scores generation quality on three dimensions: faithfulness (every claim is grounded in retrieved context), refusal correctness (out-of-scope queries are declined), and qualitative inspection of the bottom-N failures. The deterministic metrics (Hit@5, MRR, MustContain, Citation F1) don't need a judge. The faithfulness check does.

The default move is "use the same model as the generator." That's wrong here for two reasons:

1. **Self-serving bias.** A judge from the same family as the generator scores more leniently on its own outputs. This is well-documented in the LLM-as-judge literature (Zheng et al., 2023). The bias is small but real and we don't want it baking into our delta numbers.
2. **Cost.** With 30 cases and one judge call per generation case, running the eval N times during a phase of experiments adds up. The judge call dominates non-generator spend.

## Options considered

1. **`claude-sonnet-4-6` (same as generator).** Strong reasoning, but maximally biased toward its own family's outputs. ~$3 per 1M input tokens.
2. **`claude-haiku-4-5-20251001` (this ADR).** Smaller Claude, ~$0.80 per 1M input tokens. Same family as the generator, so still some bias, but the across-tier comparison is closer to the published practice in the LLM-judge papers.
3. **GPT-4o-mini (cross-provider).** Best on bias-mitigation grounds. Adds a second vendor and a second API key for one purpose. Not worth the operational complexity at this project scale.
4. **Local Llama 3 70B as judge.** Eliminates vendor cost entirely. Requires GPU infra we don't have; would dominate the project budget.

## Decision

Use `claude-haiku-4-5-20251001` as the judge for faithfulness and refusal. Pin the date string explicitly in [backend/app/config.py](../../backend/app/config.py) so a future Anthropic alias change doesn't silently shift judge scores. Run with `temperature=0` and use Anthropic tool use to enforce a strict JSON schema for the verdict — string parsing is too brittle for an evaluation surface.

We accept that this is **same-family judging** and call it out in [docs/evals.md](../evals.md) as a known limitation rather than hiding it. The relative deltas between configs (baseline vs reranked) are the load-bearing numbers; absolute faithfulness scores should be read with this caveat in mind.

## Consequences

### Positive

- **Cost.** Haiku is roughly 4x cheaper than Sonnet at this size; running the eval suite costs ~$0.50–1.00 per pass instead of ~$3.
- **Speed.** Haiku judging is fast enough (~1.5 s per case) that the full 30-case eval finishes in 5–8 minutes including generation; this matters for the iterate–measure–iterate loop the project is built around.
- **Tool-use JSON.** Anthropic's tool-use surface gives us schema-validated structured output without resorting to regex or `instructor`-style retries. The judge module ([backend/evals/judges/claude_judge.py](../../backend/evals/judges/claude_judge.py)) is ~80 lines including the rubric.
- **Predictable model identity.** Pinning the date suffix means scoring is reproducible across re-runs even after Anthropic releases a new Haiku.

### Negative

- **Same-family bias.** Sonnet writes the answer, Haiku scores it. Both are trained on overlapping data and may share blind spots. The score floor is probably higher than a cross-provider judge would produce. We don't claim absolute faithfulness numbers as a benchmark — only deltas between configs.
- **No inter-rater agreement.** With one judge, Cohen's kappa isn't measurable. Mitigation: spot-check the bottom-N cases by hand each run; the reports already surface them with the judge's reasoning visible for review.
- **Haiku's calibration on edge cases.** Smaller models are less reliable on subtle, partially-supported claims. We've seen the judge mark partial claims as fully supported on the `ambiguous` slice (n=3, so noise dominates anyway).

### When to revisit

- Adding a second-provider judge as a one-off bias-check pass on a flagship eval run. Compare distributions; if Haiku is materially more lenient on the same items, recalibrate the rubric.
- If the corpus or generator changes substantially (e.g. switching from Claude to a different family), re-run the same-family vs cross-family comparison.
- If a future paper or Anthropic release changes the relative cost equation (e.g. a much cheaper Sonnet tier), reconsider whether across-tier matters more than across-provider.

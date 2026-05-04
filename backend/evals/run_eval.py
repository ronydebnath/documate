"""DocuMate eval harness.

Loads backend/evals/dataset.yaml, runs the same retrieve+generate pipeline as
/chat (importing ChatService directly, NOT hitting HTTP), grades each case,
and writes JSON + Markdown reports under backend/evals/reports/.

Run:
    cd backend && uv run python -m evals.run_eval --config baseline
    cd backend && uv run python -m evals.run_eval --config baseline --subset factual_lookup,multi_hop
"""

from __future__ import annotations

import argparse
import json
import logging
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from app.config import REPO_ROOT, get_settings
from app.prompts.answer import SYSTEM_PROMPT, build_user_message
from app.services.embedder import embed_query  # noqa: F401  (imported to warm the model early)
from app.services.generator import Generator
from app.services.retriever import Retriever
from evals.judges.claude_judge import ClaudeJudge
from evals.metrics.generation import citation_f1, must_contain_pass
from evals.metrics.refusal import refusal_correct
from evals.metrics.retrieval import hit_at_k, mrr
from evals.schemas import (
    Aggregates,
    CaseResult,
    CategoryAggregate,
    EvalCase,
    RunReport,
)
from ingest.chroma_store import ChromaStore

log = logging.getLogger("evals.run_eval")

EVALS_DIR = Path(__file__).resolve().parent
DATASET_PATH = EVALS_DIR / "dataset.yaml"
CONFIGS_DIR = EVALS_DIR / "configs"
REPORTS_DIR = EVALS_DIR / "reports"


def load_dataset(path: Path = DATASET_PATH) -> list[EvalCase]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    return [EvalCase(**entry) for entry in raw]


def load_config(name: str) -> dict[str, Any]:
    path = CONFIGS_DIR / f"{name}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Config not found: {path}")
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _safe_mean(xs: list[float | int] | list[float]) -> float | None:
    xs = [x for x in xs if x is not None]
    if not xs:
        return None
    return float(statistics.mean(xs))


def _safe_rate(bools: list[bool | None]) -> float | None:
    vals = [int(b) for b in bools if b is not None]
    if not vals:
        return None
    return sum(vals) / len(vals)


def _aggregate(cases: list[CaseResult]) -> CategoryAggregate:
    if not cases:
        return CategoryAggregate(
            count=0,
            faithfulness=0.0,
            must_contain_pass_rate=0.0,
        )
    return CategoryAggregate(
        count=len(cases),
        hit_at_k=_safe_mean([c.hit_at_k for c in cases if c.hit_at_k is not None]),
        mrr=_safe_mean([c.mrr for c in cases if c.mrr is not None]),
        faithfulness=_safe_mean([c.faithfulness for c in cases]) or 0.0,
        citation_precision=_safe_mean(
            [c.citation_precision for c in cases if c.citation_precision is not None]
        ),
        citation_recall=_safe_mean(
            [c.citation_recall for c in cases if c.citation_recall is not None]
        ),
        citation_f1=_safe_mean(
            [c.citation_f1 for c in cases if c.citation_f1 is not None]
        ),
        must_contain_pass_rate=_safe_rate([c.must_contain_pass for c in cases]) or 0.0,
        refusal_accuracy=_safe_rate([c.refusal_correct for c in cases]),
    )


def _build_aggregates(cases: list[CaseResult]) -> Aggregates:
    by_cat: dict[str, CategoryAggregate] = {}
    for c in cases:
        by_cat.setdefault(c.category, [])  # type: ignore[arg-type]
    cats: dict[str, list[CaseResult]] = {}
    for c in cases:
        cats.setdefault(c.category, []).append(c)
    return Aggregates(
        overall=_aggregate(cases),
        by_category={cat: _aggregate(cs) for cat, cs in sorted(cats.items())},
    )


def run_one(
    case: EvalCase,
    *,
    retriever: Retriever,
    generator: Generator,
    judge: ClaudeJudge,
    top_k: int,
) -> CaseResult:
    has_expected = bool(case.expected_source_ids)

    # Retrieve
    t0 = time.monotonic()
    chunks = retriever.retrieve(case.question, top_k=top_k)
    t1 = time.monotonic()

    # Generate
    user = build_user_message(case.question, chunks)
    answer_obj = generator.generate(SYSTEM_PROMPT, user)
    t2 = time.monotonic()

    # Judge
    verdict = judge.judge(case.question, answer_obj.text, chunks)
    t3 = time.monotonic()

    retrieved_ids = [c.chunk_id for c in chunks]
    retrieved_set = set(retrieved_ids)
    cited_ids = [cid for cid in answer_obj.cited_chunk_ids if cid in retrieved_set]

    # Retrieval metrics (only when ground-truth sources exist)
    h = hit_at_k(retrieved_ids, case.expected_source_ids) if has_expected else None
    m = mrr(retrieved_ids, case.expected_source_ids) if has_expected else None

    # Citation F1: only meaningful when answering is expected.
    if case.category in ("out_of_scope", "ambiguous"):
        cit_p = cit_r = cit_f1 = None
    else:
        cit_p, cit_r, cit_f1 = citation_f1(cited_ids, case.expected_source_ids)

    # Must-contain
    mc_pass = must_contain_pass(answer_obj.text, case.must_contain, case.must_not_contain)

    # Refusal correctness
    ref_correct = refusal_correct(case.category, answer_obj.text)

    return CaseResult(
        case_id=case.id,
        category=case.category,
        question=case.question,
        answer=answer_obj.text,
        retrieved_chunk_ids=retrieved_ids,
        cited_chunk_ids=cited_ids,
        hit_at_k=h,
        mrr=m,
        faithfulness=int(verdict.faithful),
        judge_reason=verdict.reason,
        judge_parse_error=verdict.parse_error,
        citation_precision=cit_p,
        citation_recall=cit_r,
        citation_f1=cit_f1,
        must_contain_pass=mc_pass,
        refusal_correct=ref_correct,
        retrieve_ms=int((t1 - t0) * 1000),
        generate_ms=int((t2 - t1) * 1000),
        judge_ms=int((t3 - t2) * 1000),
    )


# ---------- Reports ----------

def _fmt(v: float | int | None, *, decimals: int = 2) -> str:
    if v is None:
        return "—"
    if isinstance(v, int) and not isinstance(v, bool):
        return f"{v}"
    return f"{v:.{decimals}f}"


def _markdown_overall_row(label: str, agg: CategoryAggregate) -> str:
    return (
        f"| {label} | {agg.count} | "
        f"{_fmt(agg.hit_at_k)} | {_fmt(agg.mrr)} | "
        f"{_fmt(agg.faithfulness)} | {_fmt(agg.citation_f1)} | "
        f"{_fmt(agg.must_contain_pass_rate)} | {_fmt(agg.refusal_accuracy)} |"
    )


def _format_markdown(report: RunReport) -> str:
    out: list[str] = []
    out.append(f"# Eval report — {report.config_name}")
    out.append("")
    out.append(f"- Started: `{report.started_at}`")
    out.append(f"- Finished: `{report.finished_at}`")
    out.append(f"- Cases: **{report.case_count}**")
    out.append("")
    out.append("## Overall")
    out.append("")
    out.append(
        "| Slice | n | Hit@k | MRR | Faithful | Cite F1 | MustContain | Refusal |"
    )
    out.append(
        "|-------|---|-------|-----|----------|---------|-------------|---------|"
    )
    out.append(_markdown_overall_row("**all**", report.aggregates.overall))
    for cat, agg in report.aggregates.by_category.items():
        out.append(_markdown_overall_row(cat, agg))
    out.append("")

    # Bottom 5 worst cases (sort key: faithful asc, then must_contain asc, then citation_f1 asc, then -mrr)
    def sort_key(c: CaseResult) -> tuple:
        return (
            c.faithfulness,
            int(c.must_contain_pass),
            (c.citation_f1 if c.citation_f1 is not None else 1.0),
            -(c.mrr if c.mrr is not None else 0.0),
        )

    worst = sorted(report.cases, key=sort_key)[:5]
    out.append("## Bottom 5 cases (worst first)")
    out.append("")
    for c in worst:
        out.append(f"### `{c.case_id}` · {c.category}")
        out.append("")
        out.append(f"**Question:** {c.question}")
        out.append("")
        out.append(
            f"- Hit@k={_fmt(c.hit_at_k)} · MRR={_fmt(c.mrr)} · "
            f"Faithful={c.faithfulness} · CiteF1={_fmt(c.citation_f1)} · "
            f"MustContain={'pass' if c.must_contain_pass else 'fail'}"
            f"{' · Refusal=' + ('correct' if c.refusal_correct else 'wrong') if c.refusal_correct is not None else ''}"
        )
        out.append(f"- Judge: {c.judge_reason or '—'}")
        out.append("")
        out.append("**Answer (truncated):**")
        out.append("")
        out.append("```")
        out.append((c.answer or "")[:600])
        out.append("```")
        out.append("")

    # Latency summary
    if report.cases:
        retrieves = [c.retrieve_ms for c in report.cases]
        generates = [c.generate_ms for c in report.cases]
        judges = [c.judge_ms for c in report.cases]
        out.append("## Latency (ms)")
        out.append("")
        out.append("| Phase | mean | median | max |")
        out.append("|-------|------|--------|-----|")
        for label, vals in (
            ("retrieve", retrieves),
            ("generate", generates),
            ("judge", judges),
        ):
            if vals:
                out.append(
                    f"| {label} | {int(statistics.mean(vals))} | "
                    f"{int(statistics.median(vals))} | {max(vals)} |"
                )
        out.append("")

    return "\n".join(out) + "\n"


def write_reports(report: RunReport) -> tuple[Path, Path]:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = report.started_at.replace(":", "-").replace(".", "-")
    json_path = REPORTS_DIR / f"{report.config_name}_{ts}.json"
    md_path = REPORTS_DIR / f"{report.config_name}_{ts}.md"
    json_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    md_path.write_text(_format_markdown(report), encoding="utf-8")
    return json_path, md_path


# ---------- CLI ----------

def main() -> int:
    parser = argparse.ArgumentParser(description="DocuMate eval harness")
    parser.add_argument("--config", default="baseline")
    parser.add_argument(
        "--subset",
        default=None,
        help="Comma-separated list of categories to include (e.g. factual_lookup,multi_hop)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Cap total number of cases (for smoke testing)",
    )
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    settings = get_settings()
    cfg = load_config(args.config)

    top_k = int(cfg.get("top_k", settings.retrieval_top_k))
    generator_model = cfg.get("generator_model", settings.anthropic_generator_model)
    judge_model = cfg.get("judge_model", settings.anthropic_judge_model)
    config_name = cfg.get("name", args.config)

    cases = load_dataset()
    if args.subset:
        wanted = {s.strip() for s in args.subset.split(",") if s.strip()}
        cases = [c for c in cases if c.category in wanted]
    if args.limit is not None:
        cases = cases[: args.limit]
    if not cases:
        log.error("No cases to run; check --subset and --limit")
        return 1

    log.info(
        "Config=%s top_k=%d gen=%s judge=%s cases=%d",
        config_name, top_k, generator_model, judge_model, len(cases),
    )

    store = ChromaStore(settings.chroma_persist_dir, settings.chroma_collection)
    retriever = Retriever(store)
    generator = Generator(api_key=settings.anthropic_api_key, model=generator_model)
    judge = ClaudeJudge(api_key=settings.anthropic_api_key, model=judge_model)

    started_at = datetime.now(timezone.utc).isoformat()
    results: list[CaseResult] = []
    for i, case in enumerate(cases, start=1):
        log.info("[%d/%d] %s · %s", i, len(cases), case.id, case.category)
        result = run_one(
            case,
            retriever=retriever,
            generator=generator,
            judge=judge,
            top_k=top_k,
        )
        log.info(
            "  hit@k=%s mrr=%s faithful=%d cite_f1=%s mc=%s ref=%s",
            result.hit_at_k, _fmt(result.mrr),
            result.faithfulness, _fmt(result.citation_f1),
            result.must_contain_pass, result.refusal_correct,
        )
        results.append(result)
    finished_at = datetime.now(timezone.utc).isoformat()

    report = RunReport(
        config_name=config_name,
        started_at=started_at,
        finished_at=finished_at,
        case_count=len(results),
        cases=results,
        aggregates=_build_aggregates(results),
    )
    json_path, md_path = write_reports(report)

    print()
    print("=" * 60)
    print(f"Wrote: {json_path.relative_to(REPO_ROOT)}")
    print(f"Wrote: {md_path.relative_to(REPO_ROOT)}")
    print("=" * 60)

    overall = report.aggregates.overall
    print(f"Cases:           {overall.count}")
    print(f"Hit@k:           {_fmt(overall.hit_at_k)}")
    print(f"MRR:             {_fmt(overall.mrr)}")
    print(f"Faithfulness:    {_fmt(overall.faithfulness)}")
    print(f"Citation F1:     {_fmt(overall.citation_f1)}")
    print(f"MustContain:     {_fmt(overall.must_contain_pass_rate)}")
    print(f"Refusal:         {_fmt(overall.refusal_accuracy)}")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Offline prose eval for the research formatter (rf-1 prompt, gv-1 validator).

Freeze a set of nightly report payloads once, then run the formatter over them with the
current model or prompt and compare deterministic metrics. No LLM-as-judge, no research_*
rows written, never scheduled and never run in CI. Paid runs are owner-only:

    python scripts/research_prose_eval.py freeze --n 20 --out payloads.jsonl
    python scripts/research_prose_eval.py run --in payloads.jsonl --max-calls 40 --label base --yes

See docs/research/RUNBOOK.md section 10.
"""
import argparse
import collections
import hashlib
import json
import os
import sys
from typing import Any, Callable

# Ensure we can import from backend
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

USD_PER_CALL = 0.0009  # engine spec 7.8 estimate; verify current pricing
MAX_CALLS_LIMIT = 200


def freeze(session, n: int) -> list[dict]:
    """The first `n` latest-date nightly reports in symbol-hash order, as report JSON only."""
    from sqlalchemy import func

    from models.db_models import ResearchReportRow
    from repositories import research_repo

    latest = session.query(func.max(ResearchReportRow.as_of_date)).filter(
        ResearchReportRow.origin == "nightly").scalar()
    if latest is None:
        return []
    rows = session.query(ResearchReportRow).filter(
        ResearchReportRow.origin == "nightly", ResearchReportRow.as_of_date == latest).all()
    rows.sort(key=lambda r: hashlib.sha1(r.symbol.encode()).hexdigest())
    items = []
    for row in rows[:n]:
        symbols, names = research_repo.known_symbols_and_names(session, exclude_symbol=row.symbol)
        items.append({
            "symbol": row.symbol,
            "report": row.report_json,
            "known_symbols": sorted(symbols),
            "company_names": list(names),
        })
    return items


def run_eval(payloads: list[dict], *, max_calls: int, generate: Callable) -> tuple[dict, list[dict]]:
    """Run `generate` (formatter.generate_narrative) over the payloads within the call budget."""
    remaining = max_calls
    samples: list[dict] = []
    failure_codes: collections.Counter = collections.Counter()
    prompt_version, validator_version = "rf-1", "gv-1"
    for p in payloads:
        if remaining <= 0:
            break
        narrative, attempts, failures = generate(
            p["report"], known_symbols=set(p["known_symbols"]), company_names=p["company_names"],
            allow_llm=True, calls_remaining=remaining)
        remaining -= max(attempts, 0)
        codes = [f["code"] for f in failures]
        failure_codes.update(codes)
        prompt_version = narrative.get("prompt_version", prompt_version)
        validator_version = narrative.get("validator_version", validator_version)
        samples.append({"symbol": p["symbol"], "status": narrative.get("status"), "attempts": attempts,
                        "failure_codes": codes, "narrative": narrative})
    n = len(samples)
    validated = sum(1 for s in samples if s["status"] == "llm_validated")
    template = sum(1 for s in samples if s["status"] == "template")
    first_pass = sum(1 for s in samples if s["status"] == "llm_validated" and s["attempts"] == 1)

    def rate(count: int) -> float:
        return round(count / n, 4) if n else 0.0

    try:
        from services.llm_utils import DEEPSEEK_MODEL as model
    except Exception:  # eval of the metrics must not depend on provider config
        model = "unknown"
    summary = {
        "n_evaluated": n,
        "llm_validated": validated,
        "template": template,
        "first_pass_rate": rate(first_pass),
        "validated_rate": rate(validated),
        "template_rate": rate(template),
        "mean_attempts": round(sum(s["attempts"] for s in samples) / n, 4) if n else 0.0,
        "failure_codes": dict(failure_codes),
        "calls_used": max_calls - remaining,
        "model": model,
        "prompt_version": prompt_version,
        "validator_version": validator_version,
    }
    return summary, samples


def _read_payloads(path: str) -> list[dict]:
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="research_prose_eval", description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="cmd")
    fr = sub.add_parser("freeze", help="write frozen nightly payloads as JSONL")
    fr.add_argument("--n", type=int, default=20)
    fr.add_argument("--out", required=True)
    rn = sub.add_parser("run", help="run the formatter over frozen payloads (paid DeepSeek calls)")
    rn.add_argument("--in", dest="infile", required=True)
    rn.add_argument("--max-calls", type=int, default=40)
    rn.add_argument("--label", default="run")
    rn.add_argument("--out")
    rn.add_argument("--yes", action="store_true")
    args = parser.parse_args(argv)
    if args.cmd is None:
        parser.print_usage()
        return 2

    if args.cmd == "freeze":
        if not 1 <= args.n <= 50:
            print("--n must be between 1 and 50", file=sys.stderr)
            return 2
        from database import get_session

        with get_session() as session:
            items = freeze(session, args.n)
        if not items:
            print("no nightly reports found", file=sys.stderr)
            return 2
        with open(args.out, "w", encoding="utf-8") as fh:
            for item in items:
                fh.write(json.dumps(item, sort_keys=True, default=str) + "\n")
        print(f"froze {len(items)} payloads to {args.out}")
        return 0

    if not args.yes:
        print("refusing to make paid calls without --yes", file=sys.stderr)
        return 2
    if not os.getenv("DEEPSEEK_API_KEY"):
        print("DEEPSEEK_API_KEY is not set", file=sys.stderr)
        return 2
    if not 1 <= args.max_calls <= MAX_CALLS_LIMIT:
        print(f"--max-calls must be between 1 and {MAX_CALLS_LIMIT}", file=sys.stderr)
        return 2
    payloads = _read_payloads(args.infile)
    if not payloads:
        print("the input has no payloads", file=sys.stderr)
        return 2
    print(f"This makes up to {args.max_calls} paid DeepSeek calls "
          f"(about ${args.max_calls * USD_PER_CALL:.2f} at the spec 7.8 estimate; verify current pricing).")
    from services import llm_budget
    from services.research import formatter

    llm_budget.bind(None, "prose_eval")  # attribute the ledger rows
    summary, samples = run_eval(payloads, max_calls=args.max_calls, generate=formatter.generate_narrative)
    summary = {"label": args.label, **summary}
    print(json.dumps(summary, indent=2, sort_keys=True))
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            for sample in samples:
                fh.write(json.dumps(sample, sort_keys=True, default=str) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
